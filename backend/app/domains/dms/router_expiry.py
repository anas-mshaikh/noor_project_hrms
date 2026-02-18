"""
DMS expiry rules + reporting endpoints.
"""

from __future__ import annotations


from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.db.session import get_db
from app.domains.dms.policies import require_dms_expiry_read, require_dms_expiry_write
from app.domains.dms.schemas import (
    ExpiryRuleCreateIn,
    ExpiryRuleOut,
    ExpiryRulesOut,
    UpcomingExpiryItemOut,
    UpcomingExpiryOut,
)
from app.domains.dms.service_expiry import DmsExpiryService
from app.shared.types import AuthContext


router = APIRouter(prefix="/dms/expiry", tags=["dms"])
_svc = DmsExpiryService()


@router.get("/rules")
def list_rules(
    ctx: AuthContext = Depends(require_dms_expiry_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _svc.list_rules(db, ctx=ctx)
    items = [ExpiryRuleOut(**r) for r in rows]
    return ok(ExpiryRulesOut(items=items).model_dump())


@router.post("/rules")
def create_rule(
    payload: ExpiryRuleCreateIn,
    ctx: AuthContext = Depends(require_dms_expiry_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.create_rule(
        db,
        ctx=ctx,
        document_type_code=payload.document_type_code,
        days_before=payload.days_before,
        is_active=payload.is_active,
    )
    return ok(ExpiryRuleOut(**row).model_dump())


@router.get("/upcoming")
def upcoming(
    days: int = Query(30, ge=1, le=3650),
    ctx: AuthContext = Depends(require_dms_expiry_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _svc.upcoming(db, ctx=ctx, days=days)
    items = [UpcomingExpiryItemOut(**r) for r in rows]
    return ok(UpcomingExpiryOut(items=items).model_dump())
