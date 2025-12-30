"""
stores.py

Stores belong to an organization.
"""

from __future__ import annotations
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Organization, Store

router = APIRouter(tags=["stores"])


class StoreCreateRequest(BaseModel):
    name: str
    timezone: str = "UTC"


class StoreOut(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    timezone: str
    created_at: datetime


@router.post(
    "/organizations/{org_id}/stores",
    response_model=StoreOut,
    status_code=status.HTTP_201_CREATED,
)
def create_store(
    org_id: UUID, body: StoreCreateRequest, db: Session = Depends(get_db)
) -> StoreOut:
    org = db.get(Organization, org_id)
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")

    store = Store(org_id=org_id, name=body.name, timezone=body.timezone or "UTC")
    db.add(store)
    db.commit()
    db.refresh(store)

    return StoreOut(
        id=store.id,
        org_id=store.org_id,
        name=store.name,
        timezone=store.timezone,
        created_at=store.created_at,
    )


@router.get("/organizations/{org_id}/stores", response_model=list[StoreOut])
def list_stores_for_org(org_id: UUID, db: Session = Depends(get_db)) -> list[StoreOut]:
    rows = (
        db.query(Store)
        .filter(Store.org_id == org_id)
        .order_by(Store.created_at.asc())
        .all()
    )
    return [
        StoreOut(
            id=s.id,
            org_id=s.org_id,
            name=s.name,
            timezone=s.timezone,
            created_at=s.created_at,
        )
        for s in rows
    ]


@router.get("/stores/{store_id}", response_model=StoreOut)
def get_store(store_id: UUID, db: Session = Depends(get_db)) -> StoreOut:
    s = db.get(Store, store_id)
    if s is None:
        raise HTTPException(status_code=404, detail="Store not found")

    return StoreOut(
        id=s.id,
        org_id=s.org_id,
        name=s.name,
        timezone=s.timezone,
        created_at=s.created_at,
    )
