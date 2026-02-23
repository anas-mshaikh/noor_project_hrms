"""
Payable summary recompute worker (Milestone 8).

This worker is intentionally simple in v1:
- Exposes a `run_once()` function that can be called directly (tests/cron).
- Uses the same compute service as the HTTP recompute endpoint.

We keep this separate from the CCTV/video queue workers because payroll compute
is a distinct domain concern and can be scheduled independently.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.domains.attendance.service_payable import PayableSummaryComputeService


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunPayload:
    tenant_id: UUID
    from_day: date
    to_day: date
    branch_id: UUID | None = None
    employee_ids: list[UUID] | None = None


def _resolve_employee_ids_for_branch(
    db: Session, *, tenant_id: UUID, branch_id: UUID
) -> list[UUID]:
    """
    Resolve employee_ids for a branch using current employment.

    This is a best-effort selection intended for recompute jobs; historical
    branch moves are out of scope in v1.
    """

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
    return [UUID(str(r[0])) for r in rows]


def run_once(payload: RunPayload) -> int:
    """
    Recompute payable summaries for the payload range.

    Returns:
        Number of employee-day rows computed (upserted).
    """

    svc = PayableSummaryComputeService()

    db = SessionLocal()
    try:
        employee_ids = list(payload.employee_ids or [])
        if not employee_ids:
            if payload.branch_id is None:
                raise ValueError("branch_id or employee_ids is required")
            employee_ids = _resolve_employee_ids_for_branch(
                db, tenant_id=payload.tenant_id, branch_id=payload.branch_id
            )

        computed = svc.compute_range(
            db,
            tenant_id=payload.tenant_id,
            from_day=payload.from_day,
            to_day=payload.to_day,
            branch_id=payload.branch_id,
            employee_ids=employee_ids,
            max_days=366,
        )
        return int(computed)
    finally:
        db.close()

