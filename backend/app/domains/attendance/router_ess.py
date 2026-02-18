from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.permissions import DMS_FILE_READ
from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.attendance.policies import (
    require_attendance_correction_read,
    require_attendance_correction_submit,
)
from app.domains.attendance.schemas import (
    AttendanceCorrectionCreateIn,
    AttendanceCorrectionListOut,
    AttendanceCorrectionOut,
    AttendanceDayOut,
    AttendanceDaysOut,
)
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


def _to_correction_out(row: dict) -> AttendanceCorrectionOut:
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


@router.get("/me/days")
def me_days(
    from_: date = Query(..., alias="from"),
    to: date = Query(..., alias="to"),
    ctx: AuthContext = Depends(require_attendance_correction_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _svc.get_my_days(db, ctx=ctx, start=from_, end=to)
    items = [AttendanceDayOut(**r) for r in rows]
    return ok(AttendanceDaysOut(items=items).model_dump())


@router.post("/me/corrections")
def me_submit_correction(
    payload: AttendanceCorrectionCreateIn,
    ctx: AuthContext = Depends(require_attendance_correction_submit),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if payload.evidence_file_ids and DMS_FILE_READ not in ctx.permissions:
        raise AppError(code="forbidden", message="Insufficient permission", status_code=403)

    row = _svc.create_my_correction(
        db,
        ctx=ctx,
        day=payload.day,
        correction_type=payload.correction_type,
        requested_override_status=payload.requested_override_status,
        reason=payload.reason,
        evidence_file_ids=payload.evidence_file_ids,
        idempotency_key=payload.idempotency_key,
    )
    return ok(_to_correction_out(row).model_dump())


@router.get("/me/corrections")
def me_corrections(
    status: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    ctx: AuthContext = Depends(require_attendance_correction_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cur = _parse_cursor(cursor) if cursor else None
    rows, next_cursor = _svc.list_my_corrections(db, ctx=ctx, status=status, limit=limit, cursor=cur)
    items = [_to_correction_out(r) for r in rows]
    return ok(AttendanceCorrectionListOut(items=items, next_cursor=next_cursor).model_dump())


@router.post("/me/corrections/{correction_id}/cancel")
def me_cancel_correction(
    correction_id: UUID,
    ctx: AuthContext = Depends(require_attendance_correction_submit),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.cancel_my_correction(db, ctx=ctx, correction_id=correction_id)
    return ok(_to_correction_out(row).model_dump())
