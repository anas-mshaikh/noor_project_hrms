"""
ESS endpoints for payroll payslips (Milestone 9).

Routes:
- GET  /api/v1/ess/me/payslips?year=YYYY
- GET  /api/v1/ess/me/payslips/{payslip_id}
- GET  /api/v1/ess/me/payslips/{payslip_id}/download   (raw bytes)
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.db.session import get_db
from app.domains.payroll.policies import require_payroll_payslip_read
from app.domains.payroll.schemas import PayslipListOut, PayslipOut
from app.domains.payroll.service_payslips import PayslipService
from app.shared.types import AuthContext


router = APIRouter(prefix="/ess", tags=["payroll"])
_svc = PayslipService()


@router.get("/me/payslips")
def list_my_payslips(
    year: int = Query(..., ge=2000, le=2100),
    ctx: AuthContext = Depends(require_payroll_payslip_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _svc.list_my_payslips(db, ctx=ctx, year=int(year))
    items = [PayslipOut(**r) for r in rows]
    return ok(PayslipListOut(items=items).model_dump())


@router.get("/me/payslips/{payslip_id}")
def get_my_payslip(
    payslip_id: UUID,
    ctx: AuthContext = Depends(require_payroll_payslip_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.get_my_payslip(db, ctx=ctx, payslip_id=payslip_id)
    return ok(PayslipOut(**row).model_dump())


@router.get("/me/payslips/{payslip_id}/download")
def download_my_payslip(
    payslip_id: UUID,
    ctx: AuthContext = Depends(require_payroll_payslip_read),
    db: Session = Depends(get_db),
) -> FileResponse:
    return _svc.download_my_payslip(db, ctx=ctx, payslip_id=payslip_id)

