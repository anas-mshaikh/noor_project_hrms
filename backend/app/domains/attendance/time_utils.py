"""
Attendance time utilities (Milestone 7).

Attendance punching and payroll minutes are business-day based. A "business day"
is defined by the employee's *branch timezone* (not UTC).

Why this matters:
- A punch at 23:30 UTC may belong to the next day in a UTC+3 branch.
- Payroll and "today" views must be consistent with local operations.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.errors import AppError


def get_branch_timezone(
    db: Session, *, tenant_id: UUID, branch_id: UUID
) -> ZoneInfo:
    """
    Resolve the branch timezone as a ZoneInfo object.

    - Tenant-scoped and fail-closed.
    - Falls back to UTC if the DB value is NULL/empty.
    - Raises validation_error(400) if the timezone name is invalid.
    """

    row = db.execute(
        sa.text(
            """
            SELECT timezone
            FROM tenancy.branches
            WHERE id = :branch_id
              AND tenant_id = :tenant_id
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    ).first()
    if row is None:
        raise AppError(code="validation_error", message="Branch not found", status_code=400)

    tz_name = str(row[0] or "UTC")
    try:
        return ZoneInfo(tz_name)
    except Exception as e:  # noqa: BLE001 - defensive against invalid tz database values
        raise AppError(code="validation_error", message="Invalid branch timezone", status_code=400) from e


def business_date_for_ts(ts_utc: datetime, tz: ZoneInfo) -> date:
    """
    Convert a UTC timestamp to the branch-local business date.

    This helper treats naive datetimes as UTC defensively.
    """

    if ts_utc.tzinfo is None:
        ts_utc = ts_utc.replace(tzinfo=timezone.utc)
    local = ts_utc.astimezone(tz)
    return local.date()


def utc_boundary_for_next_business_day(business_date: date, tz: ZoneInfo) -> datetime:
    """
    Return the UTC timestamp for the midnight boundary after business_date.

    Example:
    - business_date=2026-02-20, tz=Asia/Riyadh
    - returns UTC time for 2026-02-21 00:00 in Asia/Riyadh

    This is used to clamp sessions that cross local midnight.
    """

    next_day = business_date + timedelta(days=1)
    local_midnight = datetime.combine(next_day, time(0, 0), tzinfo=tz)
    return local_midnight.astimezone(timezone.utc)
