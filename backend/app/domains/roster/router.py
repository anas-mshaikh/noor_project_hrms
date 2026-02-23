"""
Roster HTTP API (Milestone 8).

All routes are under `/api/v1/roster/*` and use the standard JSON envelope.
This router is HR/admin focused (no ESS roster UI in v1).
"""

from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.roster.policies import (
    require_roster_assignment_read,
    require_roster_assignment_write,
    require_roster_defaults_write,
    require_roster_override_read,
    require_roster_override_write,
    require_roster_shift_read,
    require_roster_shift_write,
)
from app.domains.roster.schemas import (
    BranchDefaultShiftOut,
    BranchDefaultShiftUpsertIn,
    RosterOverrideOut,
    RosterOverrideUpsertIn,
    ShiftAssignmentCreateIn,
    ShiftAssignmentOut,
    ShiftTemplateCreateIn,
    ShiftTemplateOut,
    ShiftTemplatePatchIn,
)
from app.domains.roster.service_assignments import ShiftAssignmentService
from app.domains.roster.service_defaults import BranchDefaultShiftService
from app.domains.roster.service_shifts import ShiftTemplateService
from app.domains.roster.service_overrides import RosterOverrideService
from app.shared.types import AuthContext


router = APIRouter(prefix="/roster", tags=["roster"])
_shift_svc = ShiftTemplateService()
_default_svc = BranchDefaultShiftService()
_assign_svc = ShiftAssignmentService()
_override_svc = RosterOverrideService()


@router.post("/branches/{branch_id}/shifts")
def create_shift_template(
    branch_id: UUID,
    payload: ShiftTemplateCreateIn,
    ctx: AuthContext = Depends(require_roster_shift_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _shift_svc.create_shift_template(
        db,
        ctx=ctx,
        branch_id=branch_id,
        code=payload.code,
        name=payload.name,
        start_time=payload.start_time,
        end_time=payload.end_time,
        break_minutes=payload.break_minutes,
        grace_minutes=payload.grace_minutes,
        min_full_day_minutes=payload.min_full_day_minutes,
        is_active=payload.is_active,
    )
    return ok(ShiftTemplateOut(**row).model_dump())


@router.get("/branches/{branch_id}/shifts")
def list_shift_templates(
    branch_id: UUID,
    active_only: bool = Query(True),
    ctx: AuthContext = Depends(require_roster_shift_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _shift_svc.list_shift_templates(db, ctx=ctx, branch_id=branch_id, active_only=bool(active_only))
    items = [ShiftTemplateOut(**r) for r in rows]
    return ok([i.model_dump() for i in items])


@router.patch("/shifts/{shift_template_id}")
def patch_shift_template(
    shift_template_id: UUID,
    payload: ShiftTemplatePatchIn = Body(...),
    ctx: AuthContext = Depends(require_roster_shift_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    patch = payload.model_dump(exclude_none=True)
    row = _shift_svc.patch_shift_template(db, ctx=ctx, shift_template_id=shift_template_id, patch=patch)
    return ok(ShiftTemplateOut(**row).model_dump())


@router.put("/branches/{branch_id}/default-shift")
def put_default_shift(
    branch_id: UUID,
    payload: BranchDefaultShiftUpsertIn,
    ctx: AuthContext = Depends(require_roster_defaults_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _default_svc.set_default_shift(
        db,
        ctx=ctx,
        branch_id=branch_id,
        shift_template_id=payload.shift_template_id,
    )
    return ok(BranchDefaultShiftOut(**row).model_dump())


@router.get("/branches/{branch_id}/default-shift")
def get_default_shift(
    branch_id: UUID,
    ctx: AuthContext = Depends(require_roster_shift_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _default_svc.get_default_shift(db, ctx=ctx, branch_id=branch_id)
    return ok(BranchDefaultShiftOut(**row).model_dump())


@router.post("/employees/{employee_id}/assignments")
def create_employee_assignment(
    employee_id: UUID,
    payload: ShiftAssignmentCreateIn,
    ctx: AuthContext = Depends(require_roster_assignment_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _assign_svc.create_assignment(
        db,
        ctx=ctx,
        employee_id=employee_id,
        shift_template_id=payload.shift_template_id,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    return ok(ShiftAssignmentOut(**row).model_dump())


@router.get("/employees/{employee_id}/assignments")
def list_employee_assignments(
    employee_id: UUID,
    ctx: AuthContext = Depends(require_roster_assignment_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _assign_svc.list_assignments(db, ctx=ctx, employee_id=employee_id)
    items = [ShiftAssignmentOut(**r) for r in rows]
    return ok([i.model_dump() for i in items])


@router.put("/employees/{employee_id}/overrides/{day}")
def put_employee_override(
    employee_id: UUID,
    day: date,
    payload: RosterOverrideUpsertIn,
    ctx: AuthContext = Depends(require_roster_override_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _override_svc.upsert_override(
        db,
        ctx=ctx,
        employee_id=employee_id,
        day=day,
        override_type=payload.override_type,
        shift_template_id=payload.shift_template_id,
        notes=payload.notes,
    )
    return ok(RosterOverrideOut(**row).model_dump())


@router.get("/employees/{employee_id}/overrides")
def list_employee_overrides(
    employee_id: UUID,
    from_day: date = Query(..., alias="from"),
    to_day: date = Query(..., alias="to"),
    ctx: AuthContext = Depends(require_roster_override_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if from_day > to_day:
        # Keep error semantics consistent with other date range endpoints.
        raise AppError(code="validation_error", message="'from' must be <= 'to'", status_code=400)

    rows = _override_svc.list_overrides(db, ctx=ctx, employee_id=employee_id, from_day=from_day, to_day=to_day)
    items = [RosterOverrideOut(**r) for r in rows]
    return ok([i.model_dump() for i in items])
