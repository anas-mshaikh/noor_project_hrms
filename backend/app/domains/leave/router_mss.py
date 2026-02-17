from __future__ import annotations

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.leave.policies import require_leave_team_read
from app.domains.leave.schemas import TeamCalendarOut, TeamLeaveSpanOut
from app.domains.leave.service import LeaveService
from app.shared.types import AuthContext


router = APIRouter(prefix="/leave", tags=["leave"])
_svc = LeaveService()


@router.get("/team/calendar")
def team_calendar(
    from_day: date = Query(..., alias="from"),
    to_day: date = Query(..., alias="to"),
    depth: str = Query("1"),
    branch_id: UUID | None = Query(default=None),
    ctx: AuthContext = Depends(require_leave_team_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if from_day > to_day:
        raise AppError(code="leave.invalid_range", message="'from' must be <= 'to'", status_code=400)

    rows = _svc.team_calendar(db, ctx=ctx, from_day=from_day, to_day=to_day, depth=depth, branch_id=branch_id)
    items = [
        TeamLeaveSpanOut(
            leave_request_id=r["leave_request_id"],
            employee_id=r["employee_id"],
            start_date=r["start_date"],
            end_date=r["end_date"],
            leave_type_code=r["leave_type_code"],
            requested_days=float(r["requested_days"]),
        )
        for r in rows
    ]
    return ok(TeamCalendarOut(items=items).model_dump())

