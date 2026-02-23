from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Query
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.attendance.policies import (
    require_attendance_admin_read,
    require_attendance_payable_admin_read,
    require_attendance_payable_recompute,
    require_attendance_settings_write,
)
from app.domains.attendance.schemas import (
    AttendanceCorrectionListOut,
    AttendanceCorrectionOut,
    PayableDaySummaryListOut,
    PayableDaySummaryOut,
    PayableRecomputeIn,
    PayableRecomputeOut,
    PunchSettingsOut,
    PunchSettingsUpdateIn,
)
from app.domains.attendance.service import AttendanceCorrectionService
from app.domains.attendance.service_payable import PayableSummaryComputeService
from app.domains.attendance.service_punching import (
    read_or_create_punch_settings,
    update_punch_settings,
)
from app.shared.types import AuthContext


router = APIRouter(prefix="/attendance", tags=["attendance"])
_svc = AttendanceCorrectionService()
_payable_svc = PayableSummaryComputeService()


def _parse_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        ts_raw, id_raw = cursor.split("|", 1)
        ts = datetime.fromisoformat(ts_raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts, UUID(id_raw)
    except Exception as e:
        raise AppError(code="validation_error", message=f"invalid cursor: {cursor!r}", status_code=400) from e


def _to_out(row: dict) -> AttendanceCorrectionOut:
    evidence = [UUID(str(x)) for x in (row.get("evidence_file_ids") or [])]
    return AttendanceCorrectionOut(
        id=row["id"],
        tenant_id=row["tenant_id"],
        employee_id=row["employee_id"],
        branch_id=row["branch_id"],
        day=row["day"],
        correction_type=str(row["correction_type"]),
        requested_override_status=str(row["requested_override_status"]),
        reason=row.get("reason"),
        evidence_file_ids=evidence,
        status=str(row["status"]),
        workflow_request_id=row.get("workflow_request_id"),
        idempotency_key=row.get("idempotency_key"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _parse_payable_cursor(cursor: str) -> tuple[date, UUID]:
    """
    Parse a payable cursor of the form "YYYY-MM-DD|uuid".

    We order admin lists by (day DESC, employee_id DESC). The cursor keeps this
    stable and deterministic.
    """

    try:
        day_raw, emp_raw = cursor.split("|", 1)
        return date.fromisoformat(day_raw), UUID(emp_raw)
    except Exception as e:
        raise AppError(code="validation_error", message=f"invalid cursor: {cursor!r}", status_code=400) from e


@router.get("/corrections")
def admin_list_corrections(
    status: str | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = Query(default=None, alias="to"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    ctx: AuthContext = Depends(require_attendance_admin_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cur = _parse_cursor(cursor) if cursor else None
    rows, next_cursor = _svc.admin_list_corrections(
        db,
        ctx=ctx,
        status=status,
        branch_id=branch_id,
        start=from_,
        end=to,
        limit=limit,
        cursor=cur,
    )
    items = [_to_out(r) for r in rows]
    return ok(AttendanceCorrectionListOut(items=items, next_cursor=next_cursor).model_dump())


@router.get("/punch-settings")
def get_punch_settings(
    branch_id: UUID = Query(...),
    ctx: AuthContext = Depends(require_attendance_settings_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Read (or lazily initialize) punch settings for a branch.

    Security:
    - Query parameters do not automatically participate in scope resolution.
      We harden by requiring the active scope branch_id matches the requested branch.
    """

    if ctx.scope.branch_id is not None and ctx.scope.branch_id != branch_id:
        raise AppError(code="iam.scope.mismatch", message="X-Branch-Id scope mismatch", status_code=400)

    row = read_or_create_punch_settings(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id)
    # NOTE: This GET endpoint can lazily initialize defaults; commit so the row persists.
    db.commit()
    return ok(PunchSettingsOut(**row).model_dump())


@router.put("/punch-settings")
def put_punch_settings(
    payload: PunchSettingsUpdateIn,
    branch_id: UUID = Query(...),
    ctx: AuthContext = Depends(require_attendance_settings_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Create or update punch settings for a branch.

    v1 treats this as "upsert" (create if missing).
    """

    if ctx.scope.branch_id is not None and ctx.scope.branch_id != branch_id:
        raise AppError(code="iam.scope.mismatch", message="X-Branch-Id scope mismatch", status_code=400)

    row = update_punch_settings(
        db,
        tenant_id=ctx.scope.tenant_id,
        branch_id=branch_id,
        is_enabled=payload.is_enabled,
        allow_multiple_sessions_per_day=payload.allow_multiple_sessions_per_day,
        max_session_hours=payload.max_session_hours,
        require_location=payload.require_location,
        geo_fence_json=payload.geo_fence_json,
    )
    db.commit()
    return ok(PunchSettingsOut(**row).model_dump())


@router.get("/admin/payable-days")
def admin_payable_days(
    from_: date = Query(..., alias="from"),
    to: date = Query(..., alias="to"),
    branch_id: UUID | None = Query(default=None),
    employee_id: UUID | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    ctx: AuthContext = Depends(require_attendance_payable_admin_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Tenant-scoped payable summaries list for HR/admin reporting.

    v1:
    - This endpoint reads precomputed rows from attendance.payable_day_summaries.
    - For recompute, use POST /attendance/payable/recompute.
    """

    if ctx.scope.branch_id is not None:
        if branch_id is not None and branch_id != ctx.scope.branch_id:
            raise AppError(code="iam.scope.mismatch", message="X-Branch-Id scope mismatch", status_code=400)
        # Fail-closed: branch-scoped actors only see their branch.
        branch_id = ctx.scope.branch_id

    cur = _parse_payable_cursor(cursor) if cursor else None

    where = ["tenant_id = :tenant_id", "day >= :from_day", "day <= :to_day"]
    params: dict[str, Any] = {
        "tenant_id": ctx.scope.tenant_id,
        "from_day": from_,
        "to_day": to,
        "limit": int(limit),
    }
    if branch_id is not None:
        where.append("branch_id = :branch_id")
        params["branch_id"] = branch_id
    if employee_id is not None:
        where.append("employee_id = :employee_id")
        params["employee_id"] = employee_id
    if cur is not None:
        cday, cemp = cur
        where.append("(day < :cursor_day OR (day = :cursor_day AND employee_id < :cursor_employee_id))")
        params["cursor_day"] = cday
        params["cursor_employee_id"] = cemp

    sql = f"""
        SELECT *
        FROM attendance.payable_day_summaries
        WHERE {" AND ".join(where)}
        ORDER BY day DESC, employee_id DESC
        LIMIT :limit
    """
    rows = db.execute(sa.text(sql), params).mappings().all()
    items = [PayableDaySummaryOut(**dict(r)) for r in rows]

    next_cursor = None
    if len(items) == limit and rows:
        last = rows[-1]
        next_cursor = f"{last['day'].isoformat()}|{last['employee_id']}"

    return ok(PayableDaySummaryListOut(items=items, next_cursor=next_cursor).model_dump())


@router.post("/payable/recompute")
def recompute_payable_days(
    payload: PayableRecomputeIn,
    ctx: AuthContext = Depends(require_attendance_payable_recompute),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Recompute payable summaries for a range.

    Safety:
    - v1 requires either branch_id or employee_ids to be provided to avoid
      recomputing an entire tenant accidentally.
    """

    tenant_id = ctx.scope.tenant_id

    branch_id = payload.branch_id
    if ctx.scope.branch_id is not None:
        if branch_id is not None and branch_id != ctx.scope.branch_id:
            raise AppError(code="iam.scope.mismatch", message="X-Branch-Id scope mismatch", status_code=400)
        branch_id = ctx.scope.branch_id

    employee_ids = list(payload.employee_ids or [])

    if branch_id is None and not employee_ids:
        raise AppError(
            code="attendance.payable.recompute.forbidden",
            message="branch_id or employee_ids is required",
            status_code=403,
        )

    # If the caller requests a branch recompute without listing employees,
    # select employees from current employment for that branch (deterministic order).
    if branch_id is not None and not employee_ids:
        rows = db.execute(
            sa.text(
                """
                SELECT employee_id
                FROM hr_core.v_employee_current_employment
                WHERE tenant_id = :tenant_id
                  AND branch_id = :branch_id
                ORDER BY employee_id ASC
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id},
        ).all()
        employee_ids = [UUID(str(r[0])) for r in rows]

    computed = _payable_svc.compute_range(
        db,
        tenant_id=tenant_id,
        from_day=payload.from_day,
        to_day=payload.to_day,
        branch_id=branch_id,
        employee_ids=employee_ids,
        max_days=366,
    )

    return ok(PayableRecomputeOut(computed_rows=int(computed)).model_dump())
