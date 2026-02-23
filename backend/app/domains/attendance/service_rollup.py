"""
Attendance daily rollup service (Milestone 7).

`attendance.attendance_daily` is treated as a derived/denormalized table:
- Punching v1 writes immutable punches and paired work sessions
- This service recomputes daily rollups deterministically from work_sessions

This design keeps payroll minutes predictable and makes the rollup idempotent:
running the computation multiple times yields the same result for the same
underlying sessions.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session


def _json(value: Any) -> str:
    """Serialize a value to a stable JSON string for JSONB parameters."""

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True)
class DailyRollup:
    """Computed daily rollup fields for attendance.attendance_daily."""

    first_in: datetime | None
    last_out: datetime | None
    total_minutes: int
    source_breakdown: dict[str, int]
    has_open_session: bool


class DailyRollupService:
    """
    Service that recomputes daily attendance rollups from work_sessions.

    Concurrency:
    - Callers should hold the relevant work_session row lock when closing a
      session to prevent races.
    """

    def compute(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        employee_id: UUID,
        business_date: date,
    ) -> DailyRollup:
        """
        Compute the daily rollup values without writing to the database.
        """

        rows = (
            db.execute(
                sa.text(
                    """
                    SELECT start_ts, end_ts, minutes, source_start
                    FROM attendance.work_sessions
                    WHERE tenant_id = :tenant_id
                      AND branch_id = :branch_id
                      AND employee_id = :employee_id
                      AND business_date = :business_date
                      AND status IN ('CLOSED','AUTO_CLOSED')
                    ORDER BY start_ts ASC, id ASC
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "branch_id": branch_id,
                    "employee_id": employee_id,
                    "business_date": business_date,
                },
            )
            .mappings()
            .all()
        )

        first_in: datetime | None = None
        last_out: datetime | None = None
        total_minutes = 0
        source_breakdown: dict[str, int] = {}

        for r in rows:
            start_ts = r["start_ts"]
            end_ts = r["end_ts"]
            minutes = int(r["minutes"] or 0)
            src = str(r["source_start"] or "UNKNOWN")

            total_minutes += max(0, minutes)
            source_breakdown[src] = int(source_breakdown.get(src, 0)) + max(0, minutes)

            if first_in is None or (start_ts is not None and start_ts < first_in):
                first_in = start_ts
            if end_ts is not None and (last_out is None or end_ts > last_out):
                last_out = end_ts

        open_row = db.execute(
            sa.text(
                """
                SELECT 1
                FROM attendance.work_sessions
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND status = 'OPEN'
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id},
        ).first()
        has_open_session = open_row is not None

        return DailyRollup(
            first_in=first_in,
            last_out=last_out,
            total_minutes=int(total_minutes),
            source_breakdown=source_breakdown,
            has_open_session=bool(has_open_session),
        )

    def recompute_daily(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        employee_id: UUID,
        business_date: date,
    ) -> None:
        """
        Recompute and persist the daily rollup for one employee/day.

        Implementation detail:
        - We UPSERT on (branch_id, business_date, employee_id) which is the
          existing unique constraint in the baseline schema.
        - We include a `WHERE tenant_id = EXCLUDED.tenant_id` guard to avoid
          cross-tenant updates even if mis-scoped ids were ever inserted.
        """

        rollup = self.compute(
            db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            employee_id=employee_id,
            business_date=business_date,
        )

        db.execute(
            sa.text(
                """
                INSERT INTO attendance.attendance_daily (
                  id,
                  tenant_id,
                  branch_id,
                  business_date,
                  employee_id,
                  punch_in,
                  punch_out,
                  total_minutes,
                  source_breakdown,
                  has_open_session
                ) VALUES (
                  :id,
                  :tenant_id,
                  :branch_id,
                  :business_date,
                  :employee_id,
                  :punch_in,
                  :punch_out,
                  :total_minutes,
                  CAST(:source_breakdown AS jsonb),
                  :has_open_session
                )
                ON CONFLICT (branch_id, business_date, employee_id)
                DO UPDATE SET
                  punch_in = EXCLUDED.punch_in,
                  punch_out = EXCLUDED.punch_out,
                  total_minutes = EXCLUDED.total_minutes,
                  source_breakdown = EXCLUDED.source_breakdown,
                  has_open_session = EXCLUDED.has_open_session
                WHERE attendance.attendance_daily.tenant_id = EXCLUDED.tenant_id
                """
            ),
            {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "business_date": business_date,
                "employee_id": employee_id,
                "punch_in": rollup.first_in,
                "punch_out": rollup.last_out,
                "total_minutes": int(rollup.total_minutes),
                "source_breakdown": _json(rollup.source_breakdown),
                "has_open_session": bool(rollup.has_open_session),
            },
        )

