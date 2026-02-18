from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.attendance.policies import require_attendance_admin_read
from app.domains.attendance.schemas import AttendanceCorrectionListOut, AttendanceCorrectionOut
from app.domains.attendance.service import AttendanceCorrectionService
from app.shared.types import AuthContext


router = APIRouter(prefix="/attendance", tags=["attendance"])
_svc = AttendanceCorrectionService()


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

