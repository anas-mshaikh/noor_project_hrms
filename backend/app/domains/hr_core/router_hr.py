from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.hr_core.policies import require_hr_read, require_hr_write
from app.domains.hr_core.schemas import (
    EmployeeCreateIn,
    EmployeeLinkUserIn,
    EmployeePatchIn,
    EmploymentChangeIn,
)
from app.domains.hr_core.service import HRCoreService
from app.shared.types import AuthContext

router = APIRouter(prefix="/hr", tags=["HR"])
_svc = HRCoreService()


def _require_company_id(ctx: AuthContext, company_id: UUID | None) -> UUID:
    cid = company_id or ctx.scope.company_id
    if cid is None:
        raise AppError(code="invalid_scope", message="company_id is required", status_code=400)
    return cid


@router.post("/employees")
def create_employee(
    payload: EmployeeCreateIn,
    ctx: AuthContext = Depends(require_hr_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    out = _svc.create_employee(db, ctx=ctx, payload=payload)
    return ok(out.model_dump())


@router.get("/employees")
def list_employees(
    company_id: UUID | None = None,
    q: str | None = Query(default=None, min_length=1),
    status: str | None = Query(default=None, min_length=1),
    branch_id: UUID | None = None,
    org_unit_id: UUID | None = None,
    limit: int = Query(25, ge=1, le=200),
    offset: int = Query(0, ge=0),
    ctx: AuthContext = Depends(require_hr_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cid = _require_company_id(ctx, company_id)
    items, total = _svc.list_employees(
        db,
        ctx=ctx,
        company_id=cid,
        q=q,
        status=status,
        branch_id=branch_id,
        org_unit_id=org_unit_id,
        limit=limit,
        offset=offset,
    )
    return ok({"items": [i.model_dump() for i in items], "paging": {"limit": limit, "offset": offset, "total": total}})


@router.get("/employees/{employee_id}")
def get_employee(
    employee_id: UUID,
    company_id: UUID | None = None,
    ctx: AuthContext = Depends(require_hr_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cid = _require_company_id(ctx, company_id)
    out = _svc.get_employee(db, ctx=ctx, company_id=cid, employee_id=employee_id)
    return ok(out.model_dump())


@router.patch("/employees/{employee_id}")
def patch_employee(
    employee_id: UUID,
    payload: EmployeePatchIn,
    company_id: UUID | None = None,
    ctx: AuthContext = Depends(require_hr_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cid = _require_company_id(ctx, company_id)
    out = _svc.patch_employee(db, ctx=ctx, company_id=cid, employee_id=employee_id, payload=payload)
    return ok(out.model_dump())


@router.post("/employees/{employee_id}/employment")
def change_employment(
    employee_id: UUID,
    payload: EmploymentChangeIn,
    company_id: UUID | None = None,
    ctx: AuthContext = Depends(require_hr_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cid = _require_company_id(ctx, company_id)
    out = _svc.change_employment(db, ctx=ctx, company_id=cid, employee_id=employee_id, payload=payload)
    return ok(out.model_dump())


@router.get("/employees/{employee_id}/employment")
def employment_history(
    employee_id: UUID,
    company_id: UUID | None = None,
    ctx: AuthContext = Depends(require_hr_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cid = _require_company_id(ctx, company_id)
    rows = _svc.list_employment_history(db, ctx=ctx, company_id=cid, employee_id=employee_id)
    return ok([r.model_dump() for r in rows])


@router.post("/employees/{employee_id}/link-user")
def link_user(
    employee_id: UUID,
    payload: EmployeeLinkUserIn,
    company_id: UUID | None = None,
    ctx: AuthContext = Depends(require_hr_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cid = _require_company_id(ctx, company_id)
    out = _svc.link_user(db, ctx=ctx, company_id=cid, employee_id=employee_id, payload=payload)
    return ok(out.model_dump())

