from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.db.session import get_db
from app.domains.leave.policies import (
    require_leave_admin_read,
    require_leave_allocation_write,
    require_leave_policy_read,
    require_leave_policy_write,
    require_leave_type_read,
    require_leave_type_write,
)
from app.domains.leave.schemas import (
    EmployeePolicyAssignIn,
    HolidayCreateIn,
    HolidayOut,
    HolidaysOut,
    LeaveAllocationIn,
    LeaveAllocationOut,
    LeavePolicyCreateIn,
    LeavePolicyOut,
    LeavePolicyRulesIn,
    LeaveTypeCreateIn,
    LeaveTypeOut,
    WeeklyOffOut,
    WeeklyOffPutIn,
)
from app.domains.leave.service import LeaveService
from app.shared.types import AuthContext


router = APIRouter(prefix="/leave", tags=["leave"])
_svc = LeaveService()


@router.get("/types")
def list_types(
    active_only: bool = Query(default=True),
    ctx: AuthContext = Depends(require_leave_type_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _svc.list_leave_types(db, ctx=ctx, active_only=active_only)
    items = [
        LeaveTypeOut(
            id=r["id"],
            tenant_id=r["tenant_id"],
            code=r["code"],
            name=r["name"],
            is_paid=bool(r["is_paid"]),
            unit=r["unit"],
            requires_attachment=bool(r["requires_attachment"]),
            allow_negative_balance=bool(r["allow_negative_balance"]),
            max_consecutive_days=r.get("max_consecutive_days"),
            min_notice_days=r.get("min_notice_days"),
            is_active=bool(r["is_active"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]
    return ok({"items": [i.model_dump() for i in items]})


@router.post("/types")
def create_type(
    payload: LeaveTypeCreateIn,
    ctx: AuthContext = Depends(require_leave_type_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.create_leave_type(
        db,
        ctx=ctx,
        payload={
            "code": payload.code,
            "name": payload.name,
            "is_paid": payload.is_paid,
            "unit": payload.unit,
            "requires_attachment": payload.requires_attachment,
            "allow_negative_balance": payload.allow_negative_balance,
            "max_consecutive_days": payload.max_consecutive_days,
            "min_notice_days": payload.min_notice_days,
            "is_active": payload.is_active,
        },
    )
    out = LeaveTypeOut(
        id=row["id"],
        tenant_id=row["tenant_id"],
        code=row["code"],
        name=row["name"],
        is_paid=bool(row["is_paid"]),
        unit=row["unit"],
        requires_attachment=bool(row["requires_attachment"]),
        allow_negative_balance=bool(row["allow_negative_balance"]),
        max_consecutive_days=row.get("max_consecutive_days"),
        min_notice_days=row.get("min_notice_days"),
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
    return ok(out.model_dump())


@router.get("/policies")
def list_policies(
    company_id: UUID | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    ctx: AuthContext = Depends(require_leave_policy_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _svc.list_policies(db, ctx=ctx, company_id=company_id, branch_id=branch_id)
    items = [
        LeavePolicyOut(
            id=r["id"],
            tenant_id=r["tenant_id"],
            code=r["code"],
            name=r["name"],
            company_id=r.get("company_id"),
            branch_id=r.get("branch_id"),
            effective_from=r["effective_from"],
            effective_to=r.get("effective_to"),
            year_start_month=int(r["year_start_month"]),
            is_active=bool(r["is_active"]),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]
    return ok({"items": [i.model_dump() for i in items]})


@router.post("/policies")
def create_policy(
    payload: LeavePolicyCreateIn,
    ctx: AuthContext = Depends(require_leave_policy_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.create_policy(
        db,
        ctx=ctx,
        payload={
            "code": payload.code,
            "name": payload.name,
            "company_id": payload.company_id,
            "branch_id": payload.branch_id,
            "effective_from": payload.effective_from,
            "effective_to": payload.effective_to,
            "year_start_month": int(payload.year_start_month),
            "is_active": payload.is_active,
        },
    )
    out = LeavePolicyOut(
        id=row["id"],
        tenant_id=row["tenant_id"],
        code=row["code"],
        name=row["name"],
        company_id=row.get("company_id"),
        branch_id=row.get("branch_id"),
        effective_from=row["effective_from"],
        effective_to=row.get("effective_to"),
        year_start_month=int(row["year_start_month"]),
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
    return ok(out.model_dump())


@router.post("/policies/{policy_id}/rules")
def upsert_rules(
    policy_id: UUID,
    payload: LeavePolicyRulesIn,
    ctx: AuthContext = Depends(require_leave_policy_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _svc.upsert_policy_rules(
        db,
        ctx=ctx,
        policy_id=policy_id,
        rules_in=[r.model_dump() for r in payload.rules],
    )
    return ok({"ok": True})


@router.post("/employees/{employee_id}/policy")
def assign_policy(
    employee_id: UUID,
    payload: EmployeePolicyAssignIn,
    ctx: AuthContext = Depends(require_leave_policy_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _svc.assign_employee_policy(
        db,
        ctx=ctx,
        employee_id=employee_id,
        policy_id=payload.policy_id,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    return ok({"ok": True})


@router.post("/allocations")
def allocate(
    payload: LeaveAllocationIn,
    ctx: AuthContext = Depends(require_leave_allocation_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ledger_id = _svc.allocate_balance(
        db,
        ctx=ctx,
        employee_id=payload.employee_id,
        leave_type_code=payload.leave_type_code,
        year=payload.year,
        days=payload.days,
        note=payload.note,
    )
    return ok(LeaveAllocationOut(ledger_id=ledger_id).model_dump())


@router.get("/calendar/weekly-off")
def get_weekly_off(
    branch_id: UUID,
    ctx: AuthContext = Depends(require_leave_policy_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    days = _svc.get_weekly_off(db, ctx=ctx, branch_id=branch_id)
    out = WeeklyOffOut(
        tenant_id=ctx.scope.tenant_id,
        branch_id=branch_id,
        days=[{"weekday": int(d["weekday"]), "is_off": bool(d["is_off"])} for d in days],
    )
    return ok(out.model_dump())


@router.put("/calendar/weekly-off")
def put_weekly_off(
    branch_id: UUID,
    payload: WeeklyOffPutIn,
    ctx: AuthContext = Depends(require_leave_policy_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _svc.put_weekly_off(db, ctx=ctx, branch_id=branch_id, days=[d.model_dump() for d in payload.days])
    return ok({"ok": True})


@router.get("/calendar/holidays")
def list_holidays(
    branch_id: UUID | None = Query(default=None),
    from_day: date | None = Query(default=None, alias="from"),
    to_day: date | None = Query(default=None, alias="to"),
    ctx: AuthContext = Depends(require_leave_policy_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _svc.list_holidays(db, ctx=ctx, branch_id=branch_id, from_day=from_day, to_day=to_day)
    items = [
        HolidayOut(
            id=r["id"],
            tenant_id=r["tenant_id"],
            branch_id=r.get("branch_id"),
            day=r["day"],
            name=r["name"],
            created_at=r["created_at"],
        )
        for r in rows
    ]
    return ok(HolidaysOut(items=items).model_dump())


@router.post("/calendar/holidays")
def create_holiday(
    payload: HolidayCreateIn,
    ctx: AuthContext = Depends(require_leave_policy_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.create_holiday(db, ctx=ctx, branch_id=payload.branch_id, day=payload.day, name=payload.name)
    out = HolidayOut(
        id=row["id"],
        tenant_id=row["tenant_id"],
        branch_id=row.get("branch_id"),
        day=row["day"],
        name=row["name"],
        created_at=row["created_at"],
    )
    return ok(out.model_dump())


@router.get("/reports/usage")
def usage_report(
    year: int = Query(..., ge=1970, le=2100),
    branch_id: UUID | None = Query(default=None),
    leave_type_code: str | None = Query(default=None),
    ctx: AuthContext = Depends(require_leave_admin_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    # Minimal v1 aggregation from ledger + requests.
    tenant_id = ctx.scope.tenant_id
    rows = db.execute(
        sa.text(
            """
            SELECT
              lt.code AS leave_type_code,
              COUNT(DISTINCT r.id) FILTER (WHERE r.status = 'APPROVED') AS approved_requests,
              COALESCE(SUM(CASE WHEN l.source_type = 'LEAVE_REQUEST' THEN -l.delta_days ELSE 0 END), 0) AS used_days
            FROM leave.leave_types lt
            LEFT JOIN leave.leave_requests r
              ON r.tenant_id = lt.tenant_id
             AND r.leave_type_id = lt.id
             AND r.status = 'APPROVED'
             AND (CAST(:branch_id AS uuid) IS NULL OR r.branch_id = :branch_id)
            LEFT JOIN leave.leave_ledger l
              ON l.tenant_id = lt.tenant_id
             AND l.leave_type_id = lt.id
             AND l.period_year = :year
             AND l.source_type = 'LEAVE_REQUEST'
            WHERE lt.tenant_id = :tenant_id
              AND (CAST(:leave_type_code AS text) IS NULL OR lt.code = :leave_type_code)
            GROUP BY lt.code
            ORDER BY lt.code ASC
            """
        ),
        {"tenant_id": tenant_id, "year": int(year), "branch_id": branch_id, "leave_type_code": leave_type_code},
    ).mappings().all()
    return ok({"items": [dict(r) for r in rows]})
