"""
Attendance employment resolver (Milestone 7).

Punching endpoints are branch-contextual, but ESS requests do not include a
branch_id in the path. We derive the relevant branch from the employee's
current employment row to keep behavior deterministic and tenant-safe.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.errors import AppError


def resolve_current_employment(
    db: Session, *, tenant_id: UUID, employee_id: UUID
) -> dict[str, Any]:
    """
    Return the employee's current employment details.

    We rely on `hr_core.v_employee_current_employment` which selects:
    - end_date IS NULL
    - ORDER BY is_primary DESC, start_date DESC

    If no current employment exists, punching cannot be resolved to a branch
    and we fail with a clear conflict error.
    """

    row = db.execute(
        sa.text(
            """
            SELECT
              company_id,
              branch_id,
              org_unit_id,
              manager_employee_id
            FROM hr_core.v_employee_current_employment
            WHERE tenant_id = :tenant_id
              AND employee_id = :employee_id
            """
        ),
        {"tenant_id": tenant_id, "employee_id": employee_id},
    ).mappings().first()
    if row is None:
        raise AppError(
            code="attendance.punch.no_active_employment",
            message="Employee has no current employment",
            status_code=409,
        )
    return dict(row)

