from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.deps import require_permission
from app.auth.permissions import MOBILE_SYNC
from app.core.config import settings
from app.db.session import get_db
from app.mobile.repository import get_published_dataset_id
from app.mobile.service import preview_leaderboards, preview_mobile_payload, sync_mobile_for_dataset
from app.models.models import Dataset
from app.shared.types import AuthContext

router = APIRouter(tags=["mobile"])
logger = logging.getLogger(__name__)

@router.post("/branches/{branch_id}/months/{month_key}/sync-mobile")
def sync_mobile_month(
    branch_id: uuid.UUID,
    month_key: str,
    ctx: AuthContext = Depends(require_permission(MOBILE_SYNC)),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    dataset_id = get_published_dataset_id(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, month_key=month_key)
    if dataset_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="month not published")

    dataset = db.get(Dataset, dataset_id)
    if dataset is None or dataset.tenant_id != ctx.scope.tenant_id or dataset.branch_id != branch_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dataset not found")

    sync_mobile_for_dataset(
        db,
        dataset=dataset,
        month_key=month_key,
        tenant_id=ctx.scope.tenant_id,
        branch_id=branch_id,
        dry_run=settings.mobile_sync_dry_run,
    )
    return {"status": "ok", "month_key": month_key}


@router.get("/branches/{branch_id}/months/{month_key}/mobile-preview")
def mobile_preview(
    branch_id: uuid.UUID,
    month_key: str,
    limit: int = Query(default=20, ge=1, le=200),
    ctx: AuthContext = Depends(require_permission(MOBILE_SYNC)),
    db: Session = Depends(get_db),
):
    dataset_id = get_published_dataset_id(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, month_key=month_key)
    if dataset_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="month not published")

    return preview_mobile_payload(
        db,
        month_key=month_key,
        dataset_id=dataset_id,
        tenant_id=ctx.scope.tenant_id,
        branch_id=branch_id,
        limit=limit,
    )


@router.get("/branches/{branch_id}/months/{month_key}/mobile-leaderboard-preview")
def mobile_leaderboard_preview(
    branch_id: uuid.UUID,
    month_key: str,
    ctx: AuthContext = Depends(require_permission(MOBILE_SYNC)),
    db: Session = Depends(get_db),
):
    dataset_id = get_published_dataset_id(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, month_key=month_key)
    if dataset_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="month not published")

    return preview_leaderboards(
        db,
        month_key=month_key,
        dataset_id=dataset_id,
        tenant_id=ctx.scope.tenant_id,
        branch_id=branch_id,
    )
