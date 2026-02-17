from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.permissions import DMS_FILE_READ
from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.leave.policies import (
    require_leave_balance_read,
    require_leave_request_read,
    require_leave_request_submit,
)
from app.domains.leave.schemas import (
    LeaveBalancesOut,
    LeaveRequestCreateIn,
    LeaveRequestListOut,
    LeaveRequestOut,
)
from app.domains.leave.service import LeaveService
from app.shared.types import AuthContext


router = APIRouter(prefix="/leave", tags=["leave"])
_svc = LeaveService()


def _parse_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        ts_raw, id_raw = cursor.split("|", 1)
        ts = datetime.fromisoformat(ts_raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts, UUID(id_raw)
    except Exception as e:
        raise AppError(code="validation_error", message=f"invalid cursor: {cursor!r}", status_code=400) from e


def _to_request_out(row: dict) -> LeaveRequestOut:
    return LeaveRequestOut(
        id=row["id"],
        tenant_id=row["tenant_id"],
        employee_id=row["employee_id"],
        company_id=row.get("company_id"),
        branch_id=row.get("branch_id"),
        leave_type_code=str(row.get("leave_type_code") or ""),
        leave_type_name=row.get("leave_type_name"),
        policy_id=row["policy_id"],
        start_date=row["start_date"],
        end_date=row["end_date"],
        unit=str(row["unit"]),
        half_day_part=row.get("half_day_part"),
        requested_days=float(row["requested_days"]),
        reason=row.get("reason"),
        status=str(row["status"]),
        workflow_request_id=row.get("workflow_request_id"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


@router.get("/me/balances")
def me_balances(
    year: int | None = Query(default=None, ge=1970, le=2100),
    ctx: AuthContext = Depends(require_leave_balance_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if year is None:
        year = datetime.now(timezone.utc).year
    items = _svc.get_my_balances(db, ctx=ctx, year=year)
    return ok(LeaveBalancesOut(items=items).model_dump())


@router.get("/me/requests")
def me_requests(
    status: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    ctx: AuthContext = Depends(require_leave_request_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cur = _parse_cursor(cursor) if cursor else None
    rows, next_cursor = _svc.list_my_requests(db, ctx=ctx, status=status, limit=limit, cursor=cur)
    items = [_to_request_out(r) for r in rows]
    return ok(LeaveRequestListOut(items=items, next_cursor=next_cursor).model_dump())


@router.post("/me/requests")
def me_submit_request(
    payload: LeaveRequestCreateIn,
    ctx: AuthContext = Depends(require_leave_request_submit),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if payload.attachment_file_ids and DMS_FILE_READ not in ctx.permissions:
        raise AppError(code="forbidden", message="Insufficient permission", status_code=403)

    row = _svc.create_my_request(
        db,
        ctx=ctx,
        leave_type_code=payload.leave_type_code,
        start_date=payload.start_date,
        end_date=payload.end_date,
        unit=payload.unit,
        half_day_part=payload.half_day_part,
        reason=payload.reason,
        attachment_file_ids=payload.attachment_file_ids,
        idempotency_key=payload.idempotency_key,
    )
    return ok(_to_request_out(row).model_dump())


@router.post("/me/requests/{leave_request_id}/cancel")
def me_cancel_request(
    leave_request_id: UUID,
    ctx: AuthContext = Depends(require_leave_request_submit),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.cancel_my_request(db, ctx=ctx, leave_request_id=leave_request_id)
    return ok(_to_request_out(row).model_dump())
