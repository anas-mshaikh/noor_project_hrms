from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.mobile.accounts_schemas import (
    MobileAccountListOut,
    MobileProvisionIn,
    MobileProvisionOut,
    MobileResyncOut,
    MobileRevokeOut,
)
from app.mobile.accounts_service import MobileAccountService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mobile-accounts"])


def _require_admin_mode(x_admin_token: str | None = Header(default=None)) -> None:
    """
    Minimal admin guard for development.

    - If ADMIN_MODE=false, the endpoints return 404 (so they don't exist).
    - If MOBILE_SYNC_ADMIN_TOKEN is set, require it via X-Admin-Token header.

    This mirrors the existing `/stores/{store_id}/months/{month_key}/sync-mobile` guard.
    """
    if not settings.admin_mode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found")
    if settings.mobile_sync_admin_token:
        if not x_admin_token or x_admin_token != settings.mobile_sync_admin_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="unauthorized")


@router.post(
    "/stores/{store_id}/employees/{employee_id}/mobile/provision",
    response_model=MobileProvisionOut,
)
def provision_mobile_access(
    store_id: uuid.UUID,
    employee_id: uuid.UUID,
    body: MobileProvisionIn,
    db: Session = Depends(get_db),
    _auth: None = Depends(_require_admin_mode),
) -> MobileProvisionOut:
    svc = MobileAccountService(db)
    row, generated_password = svc.provision_mobile_access(
        store_id=store_id,
        employee_id=employee_id,
        email=body.email,
        phone_number=body.phone_number,
        role=body.role,
        temp_password=body.temp_password,
    )
    return MobileProvisionOut(
        firebase_uid=row.firebase_uid,
        employee_id=str(row.employee_id),
        employee_code=row.employee_code,
        active=row.active,
        generated_password=generated_password,
    )


@router.post("/employees/{employee_id}/mobile/revoke", response_model=MobileRevokeOut)
def revoke_mobile_access(
    employee_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: None = Depends(_require_admin_mode),
) -> MobileRevokeOut:
    svc = MobileAccountService(db)
    row = svc.revoke_mobile_access(employee_id=employee_id)
    return MobileRevokeOut(firebase_uid=row.firebase_uid, active=row.active)


@router.post("/mobile/resync/{firebase_uid}", response_model=MobileResyncOut)
def resync_mapping(
    firebase_uid: str,
    db: Session = Depends(get_db),
    _auth: None = Depends(_require_admin_mode),
) -> MobileResyncOut:
    svc = MobileAccountService(db)
    svc.resync_mobile_mapping(firebase_uid=firebase_uid)
    return MobileResyncOut(firebase_uid=firebase_uid, resynced=True)


@router.get("/stores/{store_id}/mobile/accounts", response_model=list[MobileAccountListOut])
def list_store_mobile_accounts(
    store_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: None = Depends(_require_admin_mode),
) -> list[MobileAccountListOut]:
    """
    List the current mobile access mappings for a store.

    Frontend use-case:
    - Show a "Mobile" column on the Employees page.
    - Decide whether to show "Provision" vs "Revoke/Resync".

    This endpoint is admin-only (guarded by ADMIN_MODE + optional X-Admin-Token).
    """
    from app.models.models import MobileAccount

    rows = (
        db.query(MobileAccount)
        .filter(MobileAccount.store_id == store_id)
        .order_by(MobileAccount.employee_code.asc())
        .all()
    )

    # NOTE: We serialize datetimes as ISO strings to keep the frontend simple.
    return [
        MobileAccountListOut(
            employee_id=str(r.employee_id),
            employee_code=r.employee_code,
            firebase_uid=r.firebase_uid,
            role=r.role,
            active=r.active,
            created_at=r.created_at.isoformat(),
            revoked_at=r.revoked_at.isoformat() if r.revoked_at else None,
        )
        for r in rows
    ]
