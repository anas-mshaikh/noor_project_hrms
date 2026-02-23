"""
Payable day summary computation (Milestone 8).

This module materializes payroll-ready day summaries into
`attendance.payable_day_summaries`.

Key ideas:
- Expected minutes come from roster scheduling (override > assignment > branch default).
- Worked minutes come from attendance (M7 punching rollups + M4 corrections/leave overrides).
- Deterministic precedence for worked minutes:
    ON_LEAVE => 0
    CORRECTION.payload.override_minutes (if present) => override
    ABSENT_OVERRIDE => 0
    else base attendance_daily.total_minutes (NULL treated as 0)
- Day type precedence:
    ON_LEAVE > roster overrides (WEEKOFF/WORKDAY) > holiday > weekly off > workday

This service is designed to be callable from:
- HTTP endpoints (compute-on-demand for small ranges)
- a future background worker (explicit recompute jobs)
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.roster.service_shifts import compute_shift_minutes


# Small-range safety guard for synchronous compute in HTTP handlers.
MAX_SYNC_RANGE_DAYS = 62


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json_canonical(value: object) -> str:
    """
    Canonical JSON encoding for idempotent-ish updates.

    We use this when inserting jsonb fields so two dicts with different key
    ordering do not produce noisy diffs in DB logs.
    """

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _validate_range(*, from_day: date, to_day: date, max_days: int) -> list[date]:
    """Validate and expand an inclusive date range."""

    if to_day < from_day:
        raise AppError(code="attendance.payable.invalid_range", message="'from' must be <= 'to'", status_code=400)

    days = (to_day - from_day).days + 1
    if days > int(max_days):
        raise AppError(
            code="attendance.payable.invalid_range",
            message=f"Range too large (max {max_days} days)",
            status_code=400,
        )

    out: list[date] = []
    cur = from_day
    while cur <= to_day:
        out.append(cur)
        cur += timedelta(days=1)
    return out


@dataclass(frozen=True)
class BranchCalendar:
    """Preloaded branch calendar for a compute window."""

    is_off_by_weekday: dict[int, bool]
    holiday_days: set[date]


def _load_weekly_off_calendar(db: Session, *, tenant_id: UUID, branch_id: UUID) -> dict[int, bool]:
    """
    Load weekly off calendar for a branch.

    Enforcement:
    - We expect 7 rows (weekday 0..6) to exist. Baseline creates these rows via
      a trigger on tenancy.branches insertion.
    """

    rows = db.execute(
        sa.text(
            """
            SELECT weekday, is_off
            FROM leave.weekly_off
            WHERE tenant_id = :tenant_id
              AND branch_id = :branch_id
            ORDER BY weekday ASC
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    ).mappings().all()

    weekdays = {int(r["weekday"]) for r in rows}
    if len(rows) != 7 or weekdays != set(range(7)):
        raise AppError(
            code="attendance.payable.calendar_missing",
            message="Weekly off calendar is not configured for the branch",
            status_code=400,
        )

    return {int(r["weekday"]): bool(r["is_off"]) for r in rows}


def _load_holidays(
    db: Session,
    *,
    tenant_id: UUID,
    branch_id: UUID,
    from_day: date,
    to_day: date,
) -> set[date]:
    """
    Load holidays for a window.

    Rule:
    - Branch holidays override global holidays for the same day.
    - "Global" means (branch_id IS NULL AND company_id IS NULL) in this repo.
    """

    rows = db.execute(
        sa.text(
            """
            SELECT day, branch_id, name
            FROM leave.holidays
            WHERE tenant_id = :tenant_id
              AND day >= :from_day
              AND day <= :to_day
              AND (
                branch_id = :branch_id
                OR (branch_id IS NULL AND company_id IS NULL)
              )
            ORDER BY day ASC, branch_id NULLS LAST, created_at ASC, id ASC
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id, "from_day": from_day, "to_day": to_day},
    ).mappings().all()

    global_days: set[date] = set()
    branch_days: set[date] = set()
    for r in rows:
        if r.get("branch_id") is None:
            global_days.add(r["day"])
        else:
            branch_days.add(r["day"])

    # Branch-specific holiday wins. Union still correct for just "is holiday" checks.
    return set(global_days) | set(branch_days)


def _resolve_employee_branches(
    db: Session,
    *,
    tenant_id: UUID,
    employee_ids: list[UUID],
    forced_branch_id: UUID | None,
) -> dict[UUID, UUID]:
    """
    Resolve branch_id for each employee for schedule/calendar resolution.

    If `forced_branch_id` is provided (admin branch recompute), we use it for
    all employees. Otherwise we resolve current branch via
    hr_core.v_employee_current_employment.
    """

    if forced_branch_id is not None:
        return {eid: forced_branch_id for eid in employee_ids}

    rows = db.execute(
        sa.text(
            """
            SELECT employee_id, branch_id
            FROM hr_core.v_employee_current_employment
            WHERE tenant_id = :tenant_id
              AND employee_id = ANY(CAST(:employee_ids AS uuid[]))
            """
        ),
        {"tenant_id": tenant_id, "employee_ids": list(employee_ids)},
    ).mappings().all()

    by_emp: dict[UUID, UUID] = {}
    for r in rows:
        by_emp[UUID(str(r["employee_id"]))] = UUID(str(r["branch_id"]))

    # Fail-closed: if any employee is missing a current employment, we treat it as
    # not found for payable computation. Callers should pass active employees only.
    missing = [str(e) for e in employee_ids if e not in by_emp]
    if missing:
        raise AppError(
            code="attendance.payable.employee.not_found",
            message="One or more employees have no current employment",
            status_code=404,
            details={"missing_employee_ids": missing[:20]},
        )

    return by_emp


def _load_branch_defaults(
    db: Session,
    *,
    tenant_id: UUID,
    branch_ids: set[UUID],
) -> dict[UUID, UUID]:
    rows = db.execute(
        sa.text(
            """
            SELECT branch_id, default_shift_template_id
            FROM roster.branch_defaults
            WHERE tenant_id = :tenant_id
              AND branch_id = ANY(CAST(:branch_ids AS uuid[]))
            """
        ),
        {"tenant_id": tenant_id, "branch_ids": list(branch_ids)},
    ).mappings().all()

    out: dict[UUID, UUID] = {}
    for r in rows:
        out[UUID(str(r["branch_id"]))] = UUID(str(r["default_shift_template_id"]))
    return out


def _load_shift_assignments(
    db: Session,
    *,
    tenant_id: UUID,
    employee_ids: list[UUID],
    from_day: date,
    to_day: date,
) -> dict[UUID, list[dict[str, Any]]]:
    """
    Load shift assignments overlapping the compute window.

    We keep selection logic in Python for v1 simplicity (ranges are small in
    compute-on-demand paths).
    """

    rows = db.execute(
        sa.text(
            """
            SELECT *
            FROM roster.shift_assignments
            WHERE tenant_id = :tenant_id
              AND employee_id = ANY(CAST(:employee_ids AS uuid[]))
              AND NOT (
                COALESCE(effective_to, '9999-12-31'::date) < :from_day
                OR :to_day < effective_from
              )
            ORDER BY employee_id ASC, effective_from DESC, created_at DESC, id DESC
            """
        ),
        {"tenant_id": tenant_id, "employee_ids": list(employee_ids), "from_day": from_day, "to_day": to_day},
    ).mappings().all()

    out: dict[UUID, list[dict[str, Any]]] = {}
    for r in rows:
        eid = UUID(str(r["employee_id"]))
        out.setdefault(eid, []).append(dict(r))
    return out


def _assignment_shift_for_day(assignments: list[dict[str, Any]], day: date) -> UUID | None:
    """
    Select the shift_template_id for a given day from preloaded assignments.

    We assume the service-level "no overlap" invariant holds, so at most one
    assignment covers a day. If multiple do, we deterministically take the first
    row (ordered by effective_from DESC).
    """

    for a in assignments:
        eff_from = a["effective_from"]
        eff_to = a.get("effective_to")
        if eff_from <= day and (eff_to is None or day <= eff_to):
            return UUID(str(a["shift_template_id"]))
    return None


def _load_roster_overrides(
    db: Session,
    *,
    tenant_id: UUID,
    employee_ids: list[UUID],
    from_day: date,
    to_day: date,
) -> dict[tuple[UUID, date], dict[str, Any]]:
    rows = db.execute(
        sa.text(
            """
            SELECT *
            FROM roster.roster_overrides
            WHERE tenant_id = :tenant_id
              AND employee_id = ANY(CAST(:employee_ids AS uuid[]))
              AND day >= :from_day
              AND day <= :to_day
            ORDER BY employee_id ASC, day ASC, created_at DESC, id DESC
            """
        ),
        {"tenant_id": tenant_id, "employee_ids": list(employee_ids), "from_day": from_day, "to_day": to_day},
    ).mappings().all()

    out: dict[tuple[UUID, date], dict[str, Any]] = {}
    for r in rows:
        k = (UUID(str(r["employee_id"])), r["day"])
        # Unique constraint ensures one row per day, but be defensive.
        if k not in out:
            out[k] = dict(r)
    return out


def _load_shift_templates(
    db: Session,
    *,
    tenant_id: UUID,
    shift_template_ids: set[UUID],
) -> dict[UUID, dict[str, Any]]:
    if not shift_template_ids:
        return {}

    rows = db.execute(
        sa.text(
            """
            SELECT *
            FROM roster.shift_templates
            WHERE tenant_id = :tenant_id
              AND id = ANY(CAST(:ids AS uuid[]))
            """
        ),
        {"tenant_id": tenant_id, "ids": list(shift_template_ids)},
    ).mappings().all()

    out: dict[UUID, dict[str, Any]] = {}
    for r in rows:
        out[UUID(str(r["id"]))] = dict(r)
    return out


def _load_attendance_daily(
    db: Session,
    *,
    tenant_id: UUID,
    employee_ids: list[UUID],
    from_day: date,
    to_day: date,
) -> dict[tuple[UUID, date], dict[str, Any]]:
    rows = db.execute(
        sa.text(
            """
            SELECT
              employee_id,
              business_date,
              total_minutes,
              punch_in,
              punch_out,
              anomalies_json,
              source_breakdown,
              has_open_session
            FROM attendance.attendance_daily
            WHERE tenant_id = :tenant_id
              AND employee_id = ANY(CAST(:employee_ids AS uuid[]))
              AND business_date >= :from_day
              AND business_date <= :to_day
            ORDER BY employee_id ASC, business_date ASC, created_at DESC, id DESC
            """
        ),
        {"tenant_id": tenant_id, "employee_ids": list(employee_ids), "from_day": from_day, "to_day": to_day},
    ).mappings().all()

    out: dict[tuple[UUID, date], dict[str, Any]] = {}
    for r in rows:
        k = (UUID(str(r["employee_id"])), r["business_date"])
        # If multiple rows exist (shouldn't), take the newest (ORDER BY created_at DESC).
        if k not in out:
            out[k] = dict(r)
    return out


def _load_day_overrides(
    db: Session,
    *,
    tenant_id: UUID,
    employee_ids: list[UUID],
    from_day: date,
    to_day: date,
) -> tuple[set[tuple[UUID, date]], dict[tuple[UUID, date], dict[str, Any]]]:
    """
    Load leave and correction overrides for the window.

    Returns:
    - leave_keys: set of (employee_id, day) where ON_LEAVE exists
    - newest_correction_by_key: newest non-leave override per (employee, day)
    """

    rows = db.execute(
        sa.text(
            """
            SELECT
              employee_id,
              day,
              status,
              payload,
              created_at,
              id
            FROM attendance.day_overrides
            WHERE tenant_id = :tenant_id
              AND employee_id = ANY(CAST(:employee_ids AS uuid[]))
              AND day >= :from_day
              AND day <= :to_day
            ORDER BY created_at DESC, id DESC
            """
        ),
        {"tenant_id": tenant_id, "employee_ids": list(employee_ids), "from_day": from_day, "to_day": to_day},
    ).mappings().all()

    leave_keys: set[tuple[UUID, date]] = set()
    corr_by_key: dict[tuple[UUID, date], dict[str, Any]] = {}

    for r in rows:
        k = (UUID(str(r["employee_id"])), r["day"])
        st = str(r["status"])

        if st == "ON_LEAVE":
            leave_keys.add(k)
            continue

        # Newest correction wins (ORDER BY created_at DESC).
        if k not in corr_by_key:
            corr_by_key[k] = dict(r)

    return leave_keys, corr_by_key


def _resolve_day_type(
    *,
    day: date,
    leave_keys: set[tuple[UUID, date]],
    employee_id: UUID,
    roster_override: dict[str, Any] | None,
    calendar: BranchCalendar,
) -> str:
    """
    Resolve day_type using v1 precedence.

    Precedence:
    1) ON_LEAVE
    2) roster override WEEKOFF/WORKDAY
    3) holiday
    4) weekly off
    5) WORKDAY
    """

    k = (employee_id, day)
    if k in leave_keys:
        return "ON_LEAVE"

    if roster_override is not None:
        ot = str(roster_override["override_type"])
        if ot == "WEEKOFF":
            return "WEEKOFF"
        if ot == "WORKDAY":
            return "WORKDAY"

    if day in calendar.holiday_days:
        return "HOLIDAY"

    if bool(calendar.is_off_by_weekday.get(day.weekday(), False)):
        return "WEEKOFF"

    return "WORKDAY"


def _resolve_shift_for_day(
    *,
    day_type: str,
    day: date,
    roster_override: dict[str, Any] | None,
    assignments: list[dict[str, Any]],
    branch_default_shift_id: UUID | None,
) -> UUID | None:
    """
    Resolve shift_template_id for a day.

    Order:
    - roster override SHIFT_CHANGE
    - roster override WORKDAY (optional shift_template_id, else fallback)
    - effective-dated assignment covering the day
    - branch default shift
    """

    if day_type != "WORKDAY":
        return None

    if roster_override is not None:
        ot = str(roster_override["override_type"])
        if ot == "SHIFT_CHANGE":
            return UUID(str(roster_override["shift_template_id"]))
        if ot == "WORKDAY":
            if roster_override.get("shift_template_id") is not None:
                return UUID(str(roster_override["shift_template_id"]))
            # else: fallthrough to assignment/default

    shift_id = _assignment_shift_for_day(assignments, day)
    if shift_id is not None:
        return shift_id

    return branch_default_shift_id


def _resolve_worked_minutes_effective(
    *,
    day: date,
    employee_id: UUID,
    base_daily: dict[str, Any] | None,
    leave_keys: set[tuple[UUID, date]],
    corr_override: dict[str, Any] | None,
) -> tuple[int, dict[str, Any] | None, dict[str, Any] | None]:
    """
    Resolve effective worked minutes and traceability fields.

    Returns:
    - worked_minutes
    - source_breakdown (copied from attendance_daily)
    - anomalies_json (base anomalies + has_open_session)
    """

    base_minutes = int(base_daily.get("total_minutes") or 0) if base_daily is not None else 0

    # Leave override always forces worked minutes to 0.
    if (employee_id, day) in leave_keys:
        worked = 0
    else:
        worked = base_minutes

        if corr_override is not None:
            st = str(corr_override["status"])
            payload = corr_override.get("payload") or {}

            if isinstance(payload, dict) and payload.get("override_minutes") is not None:
                try:
                    worked = int(payload.get("override_minutes"))
                except Exception:
                    # Defensive: ignore invalid override_minutes values.
                    pass
            elif st == "ABSENT_OVERRIDE":
                worked = 0

    source_breakdown = base_daily.get("source_breakdown") if base_daily is not None else None

    anomalies: dict[str, Any] | None
    if base_daily is None:
        anomalies = {"has_open_session": False}
    else:
        base_anom = base_daily.get("anomalies_json") or {}
        anomalies = dict(base_anom) if isinstance(base_anom, dict) else {}
        anomalies["has_open_session"] = bool(base_daily.get("has_open_session") or False)

    return int(max(worked, 0)), source_breakdown, anomalies


def _compute_presence_and_payable(*, day_type: str, expected_minutes: int, worked_minutes: int) -> tuple[str, int]:
    """
    Compute presence_status and payable_minutes for v1.

    Notes:
    - v1 is conservative: weekoffs/holidays/leave/unscheduled pay 0.
    - On workdays, payable is min(worked, expected) (if expected>0).
    """

    if day_type in ("ON_LEAVE", "HOLIDAY", "WEEKOFF", "UNSCHEDULED"):
        return "N_A", 0

    if day_type != "WORKDAY":
        # Defensive: unknown day types should not produce payable time.
        return "N_A", 0

    if int(worked_minutes) <= 0:
        return "ABSENT", 0

    payable = int(worked_minutes)
    if int(expected_minutes) > 0:
        payable = min(int(worked_minutes), int(expected_minutes))

    return "PRESENT", int(max(payable, 0))


class PayableSummaryComputeService:
    """Compute and upsert payable summaries for a set of employees over a date range."""

    def compute_range(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        from_day: date,
        to_day: date,
        branch_id: UUID | None,
        employee_ids: list[UUID],
        max_days: int = MAX_SYNC_RANGE_DAYS,
    ) -> int:
        """
        Compute summaries for [from_day, to_day] inclusive and upsert into DB.

        This method commits on success (mirrors other domain services). Callers
        should not rely on uncommitted materializations.
        """

        days = _validate_range(from_day=from_day, to_day=to_day, max_days=int(max_days))
        if not employee_ids:
            return 0

        emp_branch = _resolve_employee_branches(
            db,
            tenant_id=tenant_id,
            employee_ids=employee_ids,
            forced_branch_id=branch_id,
        )
        branch_ids: set[UUID] = set(emp_branch.values())

        # Preload branch calendars (weekly off + holidays).
        calendars: dict[UUID, BranchCalendar] = {}
        for bid in sorted(branch_ids, key=str):
            is_off_by_weekday = _load_weekly_off_calendar(db, tenant_id=tenant_id, branch_id=bid)
            holiday_days = _load_holidays(db, tenant_id=tenant_id, branch_id=bid, from_day=from_day, to_day=to_day)
            calendars[bid] = BranchCalendar(is_off_by_weekday=is_off_by_weekday, holiday_days=holiday_days)

        default_shift_by_branch = _load_branch_defaults(db, tenant_id=tenant_id, branch_ids=branch_ids)
        assignments_by_emp = _load_shift_assignments(
            db,
            tenant_id=tenant_id,
            employee_ids=employee_ids,
            from_day=from_day,
            to_day=to_day,
        )
        overrides_by_key = _load_roster_overrides(
            db,
            tenant_id=tenant_id,
            employee_ids=employee_ids,
            from_day=from_day,
            to_day=to_day,
        )

        base_daily_by_key = _load_attendance_daily(
            db,
            tenant_id=tenant_id,
            employee_ids=employee_ids,
            from_day=from_day,
            to_day=to_day,
        )
        leave_keys, corr_by_key = _load_day_overrides(
            db,
            tenant_id=tenant_id,
            employee_ids=employee_ids,
            from_day=from_day,
            to_day=to_day,
        )

        # Collect shift templates referenced by overrides/assignments/defaults.
        shift_ids: set[UUID] = set(default_shift_by_branch.values())
        for emp_rows in assignments_by_emp.values():
            for a in emp_rows:
                shift_ids.add(UUID(str(a["shift_template_id"])))
        for o in overrides_by_key.values():
            if o.get("shift_template_id") is not None:
                shift_ids.add(UUID(str(o["shift_template_id"])))

        shift_templates = _load_shift_templates(db, tenant_id=tenant_id, shift_template_ids=shift_ids)

        # Build upsert payloads for every employee-day.
        now = _utcnow()
        params_list: list[dict[str, Any]] = []

        for employee_id in employee_ids:
            emp_bid = emp_branch[employee_id]
            cal = calendars[emp_bid]
            branch_default_shift_id = default_shift_by_branch.get(emp_bid)
            assignments = assignments_by_emp.get(employee_id, [])

            for d in days:
                key = (employee_id, d)
                roster_override = overrides_by_key.get(key)

                day_type = _resolve_day_type(
                    day=d,
                    leave_keys=leave_keys,
                    employee_id=employee_id,
                    roster_override=roster_override,
                    calendar=cal,
                )

                shift_id = _resolve_shift_for_day(
                    day_type=day_type,
                    day=d,
                    roster_override=roster_override,
                    assignments=assignments,
                    branch_default_shift_id=branch_default_shift_id,
                )

                expected_minutes = 0
                if day_type == "WORKDAY" and shift_id is not None:
                    st = shift_templates.get(shift_id)
                    if st is not None:
                        expected_minutes = compute_shift_minutes(
                            start_time=st["start_time"],
                            end_time=st["end_time"],
                            break_minutes=int(st["break_minutes"] or 0),
                        )
                    else:
                        # Defensive: missing template -> treat as unscheduled.
                        shift_id = None

                # If we expected a workday but couldn't resolve a shift, mark as UNSCHEDULED.
                if day_type == "WORKDAY" and shift_id is None:
                    day_type = "UNSCHEDULED"
                    expected_minutes = 0

                base_daily = base_daily_by_key.get((employee_id, d))
                corr_override = corr_by_key.get((employee_id, d))
                worked_minutes, source_breakdown, anomalies_json = _resolve_worked_minutes_effective(
                    day=d,
                    employee_id=employee_id,
                    base_daily=base_daily,
                    leave_keys=leave_keys,
                    corr_override=corr_override,
                )

                presence_status, payable_minutes = _compute_presence_and_payable(
                    day_type=day_type,
                    expected_minutes=int(expected_minutes),
                    worked_minutes=int(worked_minutes),
                )

                params_list.append(
                    {
                        "tenant_id": tenant_id,
                        "branch_id": emp_bid,
                        "employee_id": employee_id,
                        "day": d,
                        "shift_template_id": shift_id,
                        "day_type": day_type,
                        "presence_status": presence_status,
                        "expected_minutes": int(expected_minutes),
                        "worked_minutes": int(worked_minutes),
                        "payable_minutes": int(payable_minutes),
                        "anomalies_json": _json_canonical(anomalies_json) if anomalies_json is not None else None,
                        "source_breakdown": _json_canonical(source_breakdown) if source_breakdown is not None else None,
                        "computed_at": now,
                    }
                )

        if not params_list:
            return 0

        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO attendance.payable_day_summaries (
                      tenant_id,
                      branch_id,
                      employee_id,
                      day,
                      shift_template_id,
                      day_type,
                      presence_status,
                      expected_minutes,
                      worked_minutes,
                      payable_minutes,
                      anomalies_json,
                      source_breakdown,
                      computed_at
                    ) VALUES (
                      :tenant_id,
                      :branch_id,
                      :employee_id,
                      :day,
                      :shift_template_id,
                      :day_type,
                      :presence_status,
                      :expected_minutes,
                      :worked_minutes,
                      :payable_minutes,
                      CAST(:anomalies_json AS jsonb),
                      CAST(:source_breakdown AS jsonb),
                      :computed_at
                    )
                    ON CONFLICT (tenant_id, employee_id, day)
                    DO UPDATE SET
                      branch_id = EXCLUDED.branch_id,
                      shift_template_id = EXCLUDED.shift_template_id,
                      day_type = EXCLUDED.day_type,
                      presence_status = EXCLUDED.presence_status,
                      expected_minutes = EXCLUDED.expected_minutes,
                      worked_minutes = EXCLUDED.worked_minutes,
                      payable_minutes = EXCLUDED.payable_minutes,
                      anomalies_json = EXCLUDED.anomalies_json,
                      source_breakdown = EXCLUDED.source_breakdown,
                      computed_at = EXCLUDED.computed_at
                    """
                ),
                params_list,
            )
            db.commit()
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

        return int(len(params_list))

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------
    def list_employee_summaries(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        employee_id: UUID,
        from_day: date,
        to_day: date,
    ) -> list[dict[str, Any]]:
        rows = db.execute(
            sa.text(
                """
                SELECT *
                FROM attendance.payable_day_summaries
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND day >= :from_day
                  AND day <= :to_day
                ORDER BY day ASC, id ASC
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id, "from_day": from_day, "to_day": to_day},
        ).mappings().all()
        return [dict(r) for r in rows]

