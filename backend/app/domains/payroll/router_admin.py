"""
Payroll admin HTTP API (Milestone 9).

All routes are under `/api/v1/payroll/*` and use the standard JSON envelope,
except exports which return raw bytes (CSV).
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.payroll.policies import (
    require_payroll_calendar_read,
    require_payroll_calendar_write,
    require_payroll_compensation_read,
    require_payroll_compensation_write,
    require_payroll_component_read,
    require_payroll_component_write,
    require_payroll_payrun_export,
    require_payroll_payrun_generate,
    require_payroll_payrun_publish,
    require_payroll_payrun_read,
    require_payroll_payrun_submit,
    require_payroll_structure_read,
    require_payroll_structure_write,
)
from app.domains.payroll.schemas import (
    EmployeeCompensationOut,
    EmployeeCompensationUpsertIn,
    PayrunDetailOut,
    PayrunGenerateIn,
    PayrunItemLineOut,
    PayrunItemOut,
    PayrunOut,
    PayrunPublishOut,
    PayrunSubmitApprovalOut,
    PayrollCalendarCreateIn,
    PayrollCalendarOut,
    PayrollComponentCreateIn,
    PayrollComponentOut,
    PayrollPeriodCreateIn,
    PayrollPeriodOut,
    SalaryStructureCreateIn,
    SalaryStructureDetailOut,
    SalaryStructureLineCreateIn,
    SalaryStructureLineOut,
    SalaryStructureOut,
)
from app.domains.payroll.service_calendars import PayrollCalendarService
from app.domains.payroll.service_components import PayrollComponentService
from app.domains.payroll.service_compensations import EmployeeCompensationService
from app.domains.payroll.service_exports import PayrunExportService
from app.domains.payroll.service_payslips import PayslipService
from app.domains.payroll.service_payruns import PayrunService
from app.domains.payroll.service_structures import SalaryStructureService
from app.domains.payroll.service_workflow import PayrunWorkflowService
from app.shared.types import AuthContext


router = APIRouter(prefix="/payroll", tags=["payroll"])

_calendar_svc = PayrollCalendarService()
_component_svc = PayrollComponentService()
_structure_svc = SalaryStructureService()
_comp_svc = EmployeeCompensationService()
_payrun_svc = PayrunService()
_workflow_svc = PayrunWorkflowService()
_payslip_svc = PayslipService()
_export_svc = PayrunExportService()


# ------------------------------------------------------------------
# Calendars / periods
# ------------------------------------------------------------------


@router.post("/calendars")
def create_calendar(
    payload: PayrollCalendarCreateIn,
    ctx: AuthContext = Depends(require_payroll_calendar_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _calendar_svc.create_calendar(
        db,
        ctx=ctx,
        code=payload.code,
        name=payload.name,
        currency_code=payload.currency_code,
        timezone=payload.timezone,
        is_active=payload.is_active,
    )
    return ok(PayrollCalendarOut(**row).model_dump())


@router.get("/calendars")
def list_calendars(
    ctx: AuthContext = Depends(require_payroll_calendar_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _calendar_svc.list_calendars(db, ctx=ctx)
    items = [PayrollCalendarOut(**r) for r in rows]
    return ok([i.model_dump() for i in items])


@router.post("/calendars/{calendar_id}/periods")
def create_period(
    calendar_id: UUID,
    payload: PayrollPeriodCreateIn,
    ctx: AuthContext = Depends(require_payroll_calendar_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _calendar_svc.create_period(
        db,
        ctx=ctx,
        calendar_id=calendar_id,
        period_key=payload.period_key,
        start_date=payload.start_date,
        end_date=payload.end_date,
    )
    return ok(PayrollPeriodOut(**row).model_dump())


@router.get("/calendars/{calendar_id}/periods")
def list_periods(
    calendar_id: UUID,
    year: int = Query(..., ge=2000, le=2100),
    ctx: AuthContext = Depends(require_payroll_calendar_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _calendar_svc.list_periods_by_year(db, ctx=ctx, calendar_id=calendar_id, year=int(year))
    items = [PayrollPeriodOut(**r) for r in rows]
    return ok([i.model_dump() for i in items])


# ------------------------------------------------------------------
# Components
# ------------------------------------------------------------------


@router.post("/components")
def create_component(
    payload: PayrollComponentCreateIn,
    ctx: AuthContext = Depends(require_payroll_component_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _component_svc.create_component(
        db,
        ctx=ctx,
        code=payload.code,
        name=payload.name,
        component_type=payload.component_type,
        calc_mode=payload.calc_mode,
        default_amount=payload.default_amount,
        default_percent=payload.default_percent,
        is_taxable=payload.is_taxable,
        is_active=payload.is_active,
    )
    return ok(PayrollComponentOut(**row).model_dump())


@router.get("/components")
def list_components(
    type: str | None = Query(default=None, alias="type"),
    ctx: AuthContext = Depends(require_payroll_component_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _component_svc.list_components(db, ctx=ctx, component_type=type)
    items = [PayrollComponentOut(**r) for r in rows]
    return ok([i.model_dump() for i in items])


# ------------------------------------------------------------------
# Salary structures
# ------------------------------------------------------------------


@router.post("/salary-structures")
def create_structure(
    payload: SalaryStructureCreateIn,
    ctx: AuthContext = Depends(require_payroll_structure_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _structure_svc.create_structure(
        db,
        ctx=ctx,
        code=payload.code,
        name=payload.name,
        is_active=payload.is_active,
    )
    return ok(SalaryStructureOut(**row).model_dump())


@router.post("/salary-structures/{structure_id}/lines")
def add_structure_line(
    structure_id: UUID,
    payload: SalaryStructureLineCreateIn,
    ctx: AuthContext = Depends(require_payroll_structure_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _structure_svc.add_line(
        db,
        ctx=ctx,
        structure_id=structure_id,
        component_id=payload.component_id,
        sort_order=payload.sort_order,
        calc_mode_override=payload.calc_mode_override,
        amount_override=payload.amount_override,
        percent_override=payload.percent_override,
    )
    return ok(SalaryStructureLineOut(**row).model_dump())


@router.get("/salary-structures/{structure_id}")
def get_structure_detail(
    structure_id: UUID,
    ctx: AuthContext = Depends(require_payroll_structure_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    st, lines = _structure_svc.get_structure_detail(db, ctx=ctx, structure_id=structure_id)
    out = SalaryStructureDetailOut(
        structure=SalaryStructureOut(**st),
        lines=[SalaryStructureLineOut(**l) for l in lines],
    )
    return ok(out.model_dump())


# ------------------------------------------------------------------
# Employee compensation
# ------------------------------------------------------------------


@router.post("/employees/{employee_id}/compensation")
def upsert_employee_compensation(
    employee_id: UUID,
    payload: EmployeeCompensationUpsertIn,
    ctx: AuthContext = Depends(require_payroll_compensation_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _comp_svc.upsert_compensation(
        db,
        ctx=ctx,
        employee_id=employee_id,
        currency_code=payload.currency_code,
        salary_structure_id=payload.salary_structure_id,
        base_amount=payload.base_amount,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        overrides_json=payload.overrides_json,
    )
    return ok(EmployeeCompensationOut(**row).model_dump())


@router.get("/employees/{employee_id}/compensation")
def list_employee_compensation(
    employee_id: UUID,
    ctx: AuthContext = Depends(require_payroll_compensation_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _comp_svc.list_compensations(db, ctx=ctx, employee_id=employee_id)
    items = [EmployeeCompensationOut(**r) for r in rows]
    return ok([i.model_dump() for i in items])


# ------------------------------------------------------------------
# Payruns
# ------------------------------------------------------------------


@router.post("/payruns/generate")
def generate_payrun(
    payload: PayrunGenerateIn,
    ctx: AuthContext = Depends(require_payroll_payrun_generate),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _payrun_svc.generate_payrun(
        db,
        ctx=ctx,
        calendar_id=payload.calendar_id,
        period_key=payload.period_key,
        branch_id=payload.branch_id,
        idempotency_key=payload.idempotency_key,
    )
    return ok(PayrunOut(**row).model_dump())


@router.get("/payruns/{payrun_id}")
def get_payrun(
    payrun_id: UUID,
    include_lines: int = Query(0, ge=0, le=1),
    ctx: AuthContext = Depends(require_payroll_payrun_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    detail = _payrun_svc.get_payrun(db, ctx=ctx, payrun_id=payrun_id, include_lines=bool(include_lines))
    out = PayrunDetailOut(
        payrun=PayrunOut(**detail["payrun"]),
        items=[PayrunItemOut(**r) for r in detail["items"]],
        lines=[PayrunItemLineOut(**r) for r in (detail["lines"] or [])] if detail["lines"] is not None else None,
    )
    return ok(out.model_dump())


@router.post("/payruns/{payrun_id}/submit-approval")
def submit_payrun_for_approval(
    payrun_id: UUID,
    ctx: AuthContext = Depends(require_payroll_payrun_submit),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    res = _workflow_svc.submit_for_approval(db, ctx=ctx, payrun_id=payrun_id)
    out = PayrunSubmitApprovalOut(
        payrun_id=UUID(str(res["payrun_id"])),
        workflow_request_id=UUID(str(res["workflow_request_id"])),
        status=str(res["status"]),  # type: ignore[arg-type]
    )
    return ok(out.model_dump())


@router.post("/payruns/{payrun_id}/publish")
def publish_payrun(
    payrun_id: UUID,
    ctx: AuthContext = Depends(require_payroll_payrun_publish),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    res = _payslip_svc.publish_payrun(db, ctx=ctx, payrun_id=payrun_id)
    out = PayrunPublishOut(
        payrun_id=UUID(str(res["payrun_id"])),
        published_count=int(res["published_count"]),
        status=str(res["status"]),  # type: ignore[arg-type]
    )
    return ok(out.model_dump())


@router.get("/payruns/{payrun_id}/export")
def export_payrun(
    payrun_id: UUID,
    format: str = Query("csv"),
    ctx: AuthContext = Depends(require_payroll_payrun_export),
    db: Session = Depends(get_db),
) -> Response:
    if (format or "").lower() != "csv":
        raise AppError(code="validation_error", message="Only format=csv is supported in v1", status_code=400)

    data = _export_svc.export_payrun_csv(db, ctx=ctx, payrun_id=payrun_id)
    filename = f"payrun_{payrun_id}.csv"
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
