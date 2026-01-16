from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.mobile.repository import (
    get_published_dataset_id,
    resolve_store_org,
)
from app.mobile.service import preview_leaderboards, preview_mobile_payload, sync_mobile_for_dataset
from app.models.models import Dataset

router = APIRouter(tags=["mobile"])
logger = logging.getLogger(__name__)


def _require_mobile_admin(x_admin_token: str | None = Header(default=None)) -> None:
    if not settings.mobile_sync_admin_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if settings.mobile_sync_admin_token:
        if not x_admin_token or x_admin_token != settings.mobile_sync_admin_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


@router.post("/stores/{store_id}/months/{month_key}/sync-mobile")
def sync_mobile_month(
    store_id: uuid.UUID,
    month_key: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(_require_mobile_admin),
) -> dict[str, str]:
    dataset_id = get_published_dataset_id(db, month_key)
    if dataset_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="month not published")

    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dataset not found")

    store, org = resolve_store_org(db, store_id)
    sync_mobile_for_dataset(
        db,
        dataset=dataset,
        month_key=month_key,
        store_id=store.id,
        org_id=org.id,
        dry_run=settings.mobile_sync_dry_run,
    )
    return {"status": "ok", "month_key": month_key}


@router.get("/stores/{store_id}/months/{month_key}/mobile-preview")
def mobile_preview(
    store_id: uuid.UUID,
    month_key: str,
    limit: int = Query(default=20, ge=1, le=200),
    db: Session = Depends(get_db),
    _auth: None = Depends(_require_mobile_admin),
):
    dataset_id = get_published_dataset_id(db, month_key)
    if dataset_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="month not published")

    store, org = resolve_store_org(db, store_id)
    return preview_mobile_payload(
        db,
        month_key=month_key,
        dataset_id=dataset_id,
        store_id=store.id,
        org_id=org.id,
        limit=limit,
    )


@router.get("/stores/{store_id}/months/{month_key}/mobile-leaderboard-preview")
def mobile_leaderboard_preview(
    store_id: uuid.UUID,
    month_key: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(_require_mobile_admin),
):
    dataset_id = get_published_dataset_id(db, month_key)
    if dataset_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="month not published")

    store, org = resolve_store_org(db, store_id)
    return preview_leaderboards(
        db,
        month_key=month_key,
        dataset_id=dataset_id,
        store_id=store.id,
        org_id=org.id,
    )
