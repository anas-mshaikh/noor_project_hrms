"""
organizations.py

Basic org CRUD so you can seed data via Swagger.
Auth/RBAC comes later; for now it's open.
"""

from __future__ import annotations
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.models import Organization

router = APIRouter(tags=["organizations"])


class OrganizationCreateRequest(BaseModel):
    name: str


class OrganizationOut(BaseModel):
    id: UUID
    name: str
    created_at: datetime


@router.post(
    "/organizations",
    response_model=OrganizationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(
    body: OrganizationCreateRequest, db: Session = Depends(get_db)
) -> OrganizationOut:
    org = Organization(name=body.name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return OrganizationOut(id=org.id, name=org.name, created_at=org.created_at)


@router.get("/organizations", response_model=list[OrganizationOut])
def list_organizations(db: Session = Depends(get_db)) -> list[OrganizationOut]:
    rows = db.query(Organization).order_by(Organization.created_at.asc()).all()
    return [
        OrganizationOut(id=o.id, name=o.name, created_at=o.created_at) for o in rows
    ]
