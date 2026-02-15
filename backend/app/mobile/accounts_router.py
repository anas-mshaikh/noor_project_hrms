from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.deps import require_permission
from app.auth.permissions import MOBILE_ACCOUNTS_READ, MOBILE_ACCOUNTS_WRITE
from app.db.session import get_db
from app.mobile.accounts_schemas import (
    MobileAccountListOut,
    MobileProvisionIn,
    MobileProvisionOut,
    MobileResyncOut,
    MobileRevokeOut,
)
from app.mobile.accounts_service import MobileAccountService
from app.models.models import MobileAccount
from app.shared.types import AuthContext

logger = logging.getLogger(__name__)

router = APIRouter(tags=["mobile-accounts"])


@router.post(
    "/branches/{branch_id}/employees/{employee_id}/mobile/provision",
    response_model=MobileProvisionOut,
)
def provision_mobile_access(
    branch_id: uuid.UUID,
    employee_id: uuid.UUID,
    body: MobileProvisionIn,
    ctx: AuthContext = Depends(require_permission(MOBILE_ACCOUNTS_WRITE)),
    db: Session = Depends(get_db),
) -> MobileProvisionOut:
    svc = MobileAccountService(db)
    try:
        row, generated_password = svc.provision_mobile_access(
            tenant_id=ctx.scope.tenant_id,
            branch_id=branch_id,
            employee_id=employee_id,
            email=body.email,
            phone_number=body.phone_number,
            role=body.role,
            temp_password=body.temp_password,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)) from e
    return MobileProvisionOut(
        firebase_uid=row.firebase_uid,
        employee_id=str(row.employee_id),
        employee_code=row.employee_code,
        active=row.active,
        generated_password=generated_password,
    )


@router.post("/branches/{branch_id}/employees/{employee_id}/mobile/revoke", response_model=MobileRevokeOut)
def revoke_mobile_access(
    branch_id: uuid.UUID,
    employee_id: uuid.UUID,
    ctx: AuthContext = Depends(require_permission(MOBILE_ACCOUNTS_WRITE)),
    db: Session = Depends(get_db),
) -> MobileRevokeOut:
    svc = MobileAccountService(db)
    try:
        row = svc.revoke_mobile_access(employee_id=employee_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    if row.tenant_id != ctx.scope.tenant_id or row.branch_id != branch_id:
        # Avoid leaking whether the employee has a mapping in another branch.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="mobile account not found")
    return MobileRevokeOut(firebase_uid=row.firebase_uid, active=row.active)


@router.post("/mobile/resync/{firebase_uid}", response_model=MobileResyncOut)
def resync_mapping(
    firebase_uid: str,
    ctx: AuthContext = Depends(require_permission(MOBILE_ACCOUNTS_WRITE)),
    db: Session = Depends(get_db),
) -> MobileResyncOut:
    svc = MobileAccountService(db)
    try:
        svc.resync_mobile_mapping(firebase_uid=firebase_uid)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    return MobileResyncOut(firebase_uid=firebase_uid, resynced=True)


@router.get("/branches/{branch_id}/mobile/accounts", response_model=list[MobileAccountListOut])
def list_branch_mobile_accounts(
    branch_id: uuid.UUID,
    ctx: AuthContext = Depends(require_permission(MOBILE_ACCOUNTS_READ)),
    db: Session = Depends(get_db),
) -> list[MobileAccountListOut]:
    """
    List the current mobile access mappings for a branch.

    Frontend use-case:
    - Show a "Mobile" column on the Employees page.
    - Decide whether to show "Provision" vs "Revoke/Resync".

    This endpoint is permission-gated via RBAC (`mobile:accounts:read`).
    """
    rows = (
        db.query(MobileAccount)
        .filter(MobileAccount.tenant_id == ctx.scope.tenant_id, MobileAccount.branch_id == branch_id)
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
