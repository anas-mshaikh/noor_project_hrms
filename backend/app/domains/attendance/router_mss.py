"""
MSS/team attendance endpoints (Milestone 8).

This router adds a payroll-ready "team payable days" view for managers.
It reuses the existing MSS team graph selection logic (hr_core.repo_mss).
"""

from __future__ import annotations

from datetime import date

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.attendance.policies import require_attendance_payable_team_read
from app.domains.attendance.schemas import PayableDaySummaryOut, PayableDaysOut
from app.domains.attendance.service_payable import PayableSummaryComputeService
from app.domains.hr_core import repo_mss
from app.shared.types import AuthContext


router = APIRouter(prefix="/attendance", tags=["attendance"])
_payable_svc = PayableSummaryComputeService()


@router.get("/team/payable-days")
def team_payable_days(
    from_: date = Query(..., alias="from"),
    to: date = Query(..., alias="to"),
    depth: str = Query("1"),
    ctx: AuthContext = Depends(require_attendance_payable_team_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Return payable summaries for the manager's team (MSS).

    v1:
    - Uses `hr_core.repo_mss.list_team_directory` to determine the subtree.
    - Computes summaries on demand for small ranges and returns a flat list of rows.
    """

    actor = repo_mss.get_actor_employee_context(db, user_id=ctx.user_id)
    if actor is None:
        raise AppError(code="ess.not_linked", message="User is not linked to an employee", status_code=409)

    # We intentionally keep this unpaginated for v1 by setting a high limit.
    # Future: switch to cursor pagination if needed.
    team_rows, _total = repo_mss.list_team_directory(
        db,
        tenant_id=actor.tenant_id,
        company_id=actor.company_id,
        actor_employee_id=actor.employee_id,
        depth_mode=str(depth),
        q=None,
        status="ACTIVE",
        branch_id=None,
        org_unit_id=None,
        limit=5000,
        offset=0,
    )
    employee_ids = [r.employee_id for r in team_rows]

    if not employee_ids:
        return ok(PayableDaysOut(items=[]).model_dump())

    _payable_svc.compute_range(
        db,
        tenant_id=ctx.scope.tenant_id,
        from_day=from_,
        to_day=to,
        branch_id=None,
        employee_ids=employee_ids,
    )

    rows = db.execute(
        sa.text(
            """
            SELECT *
            FROM attendance.payable_day_summaries
            WHERE tenant_id = :tenant_id
              AND employee_id = ANY(CAST(:employee_ids AS uuid[]))
              AND day >= :from_day
              AND day <= :to_day
            ORDER BY employee_id ASC, day ASC, id ASC
            """
        ),
        {"tenant_id": ctx.scope.tenant_id, "employee_ids": list(employee_ids), "from_day": from_, "to_day": to},
    ).mappings().all()

    items = [PayableDaySummaryOut(**dict(r)) for r in rows]
    return ok(PayableDaysOut(items=items).model_dump())
