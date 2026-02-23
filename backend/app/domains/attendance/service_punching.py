"""
Attendance punching service (Milestone 7).

This service implements a Zoho-style punch-in/out toggle:
- Punch events are immutable (attendance.punches)
- Work sessions are paired state derived from punches (attendance.work_sessions)

We keep the system future-proof by storing a punch "source" and optional
source references so biometric/CCTV/import pipelines can insert punches later.

Important constraints:
- Tenant isolation is enforced on every query (fail-closed).
- ESS routes hardcode source=MANUAL_WEB in v1; clients cannot claim BIOMETRIC/CCTV.
- Work sessions allow multiple sessions per day by default (branch setting).
- We block punch-in on ON_LEAVE days; punch-out is allowed to avoid trapping.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Any, Literal
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.attendance.employment import resolve_current_employment
from app.domains.attendance.service_rollup import DailyRollupService
from app.domains.attendance.time_utils import (
    business_date_for_ts,
    get_branch_timezone,
    utc_boundary_for_next_business_day,
)
from app.shared.types import AuthContext


PunchAction = Literal["IN", "OUT"]
PunchSource = Literal[
    "MANUAL_WEB",
    "MANUAL_MOBILE",
    "SYSTEM",
    "BIOMETRIC",
    "CCTV",
    "IMPORT",
]


def utcnow() -> datetime:
    """
    UTC clock for the punching system.

    Tests monkeypatch this function to make minute computations deterministic.
    """

    return datetime.now(timezone.utc)


def _json_canonical(value: Any) -> str:
    """
    Serialize a Python value into a stable JSON string for JSONB binds.

    We intentionally keep JSON serialization deterministic to support stable
    idempotency comparisons and predictable DB writes.
    """

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True)
class ActorEmployee:
    """Resolved ESS actor linkage (employee_id + tenant/company)."""

    employee_id: UUID
    tenant_id: UUID
    company_id: UUID


def _get_actor_employee_or_409(db: Session, *, ctx: AuthContext) -> ActorEmployee:
    """
    Resolve the employee linked to the current user.

    Mirrors other domains (leave/attendance/profile-change):
    - not linked => 409 ess.not_linked
    """

    tenant_id = ctx.scope.tenant_id
    row = db.execute(
        sa.text(
            """
            SELECT e.id AS employee_id, e.company_id
            FROM hr_core.employee_user_links l
            JOIN hr_core.employees e ON e.id = l.employee_id
            WHERE l.user_id = :user_id
              AND e.tenant_id = :tenant_id
            LIMIT 1
            """
        ),
        {"user_id": ctx.user_id, "tenant_id": tenant_id},
    ).first()
    if row is None:
        raise AppError(code="ess.not_linked", message="User is not linked to an employee", status_code=409)

    employee_id, company_id = row
    return ActorEmployee(employee_id=UUID(str(employee_id)), tenant_id=tenant_id, company_id=UUID(str(company_id)))


@dataclass(frozen=True)
class PunchSettingsRow:
    """Branch-scoped settings used by the punching system."""

    is_enabled: bool
    allow_multiple_sessions_per_day: bool
    max_session_hours: int


def get_or_create_punch_settings(
    db: Session, *, tenant_id: UUID, branch_id: UUID
) -> PunchSettingsRow:
    """
    Read punch settings for a branch; lazily create defaults if missing.

    Defaults are safe for v1:
    - enabled
    - allow multiple sessions
    - max 16 hours per session
    """

    row = db.execute(
        sa.text(
            """
            SELECT is_enabled, allow_multiple_sessions_per_day, max_session_hours
            FROM attendance.punch_settings
            WHERE tenant_id = :tenant_id
              AND branch_id = :branch_id
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    ).mappings().first()
    if row is not None:
        return PunchSettingsRow(
            is_enabled=bool(row["is_enabled"]),
            allow_multiple_sessions_per_day=bool(row["allow_multiple_sessions_per_day"]),
            max_session_hours=int(row["max_session_hours"] or 16),
        )

    # Lazy create a default row (idempotent if a concurrent request inserts it).
    db.execute(
        sa.text(
            """
            INSERT INTO attendance.punch_settings (
              tenant_id,
              branch_id,
              is_enabled,
              allow_multiple_sessions_per_day,
              max_session_hours
            ) VALUES (
              :tenant_id,
              :branch_id,
              true,
              true,
              16
            )
            ON CONFLICT DO NOTHING
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    )

    row2 = db.execute(
        sa.text(
            """
            SELECT is_enabled, allow_multiple_sessions_per_day, max_session_hours
            FROM attendance.punch_settings
            WHERE tenant_id = :tenant_id
              AND branch_id = :branch_id
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    ).mappings().first()
    # Defensive: row must exist after insert attempt.
    if row2 is None:
        return PunchSettingsRow(is_enabled=True, allow_multiple_sessions_per_day=True, max_session_hours=16)

    return PunchSettingsRow(
        is_enabled=bool(row2["is_enabled"]),
        allow_multiple_sessions_per_day=bool(row2["allow_multiple_sessions_per_day"]),
        max_session_hours=int(row2["max_session_hours"] or 16),
    )


def update_punch_settings(
    db: Session,
    *,
    tenant_id: UUID,
    branch_id: UUID,
    is_enabled: bool | None,
    allow_multiple_sessions_per_day: bool | None,
    max_session_hours: int | None,
    require_location: bool | None,
    geo_fence_json: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Update punch settings for a branch (admin endpoint).

    We use an UPSERT so callers can treat PUT as "create or update".
    """

    # Ensure the branch exists in the tenant (fail-closed).
    exists = db.execute(
        sa.text(
            """
            SELECT 1
            FROM tenancy.branches
            WHERE id = :branch_id
              AND tenant_id = :tenant_id
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    ).first()
    if exists is None:
        raise AppError(code="validation_error", message="Branch not found", status_code=400)

    row = db.execute(
        sa.text(
            """
            INSERT INTO attendance.punch_settings (
              tenant_id,
              branch_id,
              is_enabled,
              allow_multiple_sessions_per_day,
              max_session_hours,
              require_location,
              geo_fence_json
            ) VALUES (
              :tenant_id,
              :branch_id,
              COALESCE(:is_enabled, true),
              COALESCE(:allow_multiple_sessions_per_day, true),
              COALESCE(:max_session_hours, 16),
              COALESCE(:require_location, false),
              CAST(:geo_fence_json AS jsonb)
            )
            ON CONFLICT (tenant_id, branch_id)
            DO UPDATE SET
              is_enabled = COALESCE(:is_enabled, attendance.punch_settings.is_enabled),
              allow_multiple_sessions_per_day = COALESCE(
                :allow_multiple_sessions_per_day,
                attendance.punch_settings.allow_multiple_sessions_per_day
              ),
              max_session_hours = COALESCE(:max_session_hours, attendance.punch_settings.max_session_hours),
              require_location = COALESCE(:require_location, attendance.punch_settings.require_location),
              geo_fence_json = COALESCE(CAST(:geo_fence_json AS jsonb), attendance.punch_settings.geo_fence_json),
              updated_at = now()
            RETURNING
              tenant_id,
              branch_id,
              is_enabled,
              allow_multiple_sessions_per_day,
              max_session_hours,
              require_location,
              geo_fence_json,
              created_at,
              updated_at
            """
        ),
        {
            "tenant_id": tenant_id,
            "branch_id": branch_id,
            "is_enabled": is_enabled,
            "allow_multiple_sessions_per_day": allow_multiple_sessions_per_day,
            "max_session_hours": max_session_hours,
            "require_location": require_location,
            "geo_fence_json": _json_canonical(geo_fence_json) if geo_fence_json is not None else None,
        },
    ).mappings().first()
    if row is None:
        raise AppError(code="internal_error", message="Failed to update punch settings", status_code=500)
    return dict(row)


def read_or_create_punch_settings(
    db: Session, *, tenant_id: UUID, branch_id: UUID
) -> dict[str, Any]:
    """
    Read punch settings for a branch, lazily inserting defaults if missing.

    This helper is used by admin endpoints so the UI can treat punch settings as
    always present for a branch once punching is introduced.
    """

    # Ensure the branch exists in the tenant (fail-closed).
    exists = db.execute(
        sa.text(
            """
            SELECT 1
            FROM tenancy.branches
            WHERE id = :branch_id
              AND tenant_id = :tenant_id
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    ).first()
    if exists is None:
        raise AppError(code="validation_error", message="Branch not found", status_code=400)

    row = db.execute(
        sa.text(
            """
            SELECT
              tenant_id,
              branch_id,
              is_enabled,
              allow_multiple_sessions_per_day,
              max_session_hours,
              require_location,
              geo_fence_json,
              created_at,
              updated_at
            FROM attendance.punch_settings
            WHERE tenant_id = :tenant_id
              AND branch_id = :branch_id
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    ).mappings().first()
    if row is not None:
        return dict(row)

    # Insert defaults without changing updated_at for existing rows.
    db.execute(
        sa.text(
            """
            INSERT INTO attendance.punch_settings (
              tenant_id,
              branch_id,
              is_enabled,
              allow_multiple_sessions_per_day,
              max_session_hours,
              require_location,
              geo_fence_json
            ) VALUES (
              :tenant_id,
              :branch_id,
              true,
              true,
              16,
              false,
              NULL
            )
            ON CONFLICT DO NOTHING
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    )

    row2 = db.execute(
        sa.text(
            """
            SELECT
              tenant_id,
              branch_id,
              is_enabled,
              allow_multiple_sessions_per_day,
              max_session_hours,
              require_location,
              geo_fence_json,
              created_at,
              updated_at
            FROM attendance.punch_settings
            WHERE tenant_id = :tenant_id
              AND branch_id = :branch_id
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    ).mappings().first()
    if row2 is None:
        raise AppError(code="internal_error", message="Failed to initialize punch settings", status_code=500)
    return dict(row2)


class PunchService:
    """
    Core punching service (ESS-focused).

    The service mutates:
    - attendance.punches (immutable)
    - attendance.work_sessions (OPEN/CLOSED)
    - attendance.attendance_daily (rollup convenience)
    """

    def __init__(self) -> None:
        self._rollup = DailyRollupService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def punch_in(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        idempotency_key: str | None,
        source: PunchSource,
        meta: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Record a punch-in and open a work session.
        """

        actor = _get_actor_employee_or_409(db, ctx=ctx)
        employment = resolve_current_employment(db, tenant_id=actor.tenant_id, employee_id=actor.employee_id)

        # Optional scope hardening: if the token is explicitly scoped to a company/branch,
        # refuse punching in a different context.
        if ctx.scope.company_id is not None and ctx.scope.company_id != employment["company_id"]:
            raise AppError(code="iam.scope.mismatch", message="X-Company-Id scope mismatch", status_code=400)
        if ctx.scope.branch_id is not None and ctx.scope.branch_id != employment["branch_id"]:
            raise AppError(code="iam.scope.mismatch", message="X-Branch-Id scope mismatch", status_code=400)

        branch_id = UUID(str(employment["branch_id"]))
        settings = get_or_create_punch_settings(db, tenant_id=actor.tenant_id, branch_id=branch_id)

        # Branch can disable punching. We block punch-in, but allow punch-out when OPEN exists.
        if not settings.is_enabled:
            raise AppError(code="attendance.punch.disabled", message="Punching is disabled for this branch", status_code=409)

        now_ts = utcnow()
        tz = get_branch_timezone(db, tenant_id=actor.tenant_id, branch_id=branch_id)
        business_date = business_date_for_ts(now_ts, tz)

        # Leave override wins: do not allow punching in on an ON_LEAVE day.
        leave = db.execute(
            sa.text(
                """
                SELECT 1
                FROM attendance.day_overrides
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND day = :day
                  AND status = 'ON_LEAVE'
                LIMIT 1
                """
            ),
            {"tenant_id": actor.tenant_id, "employee_id": actor.employee_id, "day": business_date},
        ).first()
        if leave is not None:
            raise AppError(
                code="attendance.punch.conflict.leave",
                message="Cannot punch in on a day that is on leave",
                status_code=409,
            )

        # Idempotency: prevent double-inserts for client retries.
        if idempotency_key:
            existing = db.execute(
                sa.text(
                    """
                    SELECT action
                    FROM attendance.punches
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                      AND idempotency_key = :idempotency_key
                    LIMIT 1
                    """
                ),
                {
                    "tenant_id": actor.tenant_id,
                    "employee_id": actor.employee_id,
                    "idempotency_key": idempotency_key,
                },
            ).first()
            if existing is not None:
                existing_action = str(existing[0])
                if existing_action == "IN":
                    return self.get_punch_state(db, ctx=ctx)
                raise AppError(
                    code="attendance.punch.idempotency.conflict",
                    message="Idempotency key already used for a different punch action",
                    status_code=409,
                )

        # Concurrency safety: if there is an OPEN session, the employee is already punched in.
        open_row = db.execute(
            sa.text(
                """
                SELECT id
                FROM attendance.work_sessions
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND status = 'OPEN'
                LIMIT 1
                """
            ),
            {"tenant_id": actor.tenant_id, "employee_id": actor.employee_id},
        ).first()
        if open_row is not None:
            raise AppError(code="attendance.punch.already_in", message="Already punched in", status_code=409)

        # Optional constraint: limit to one session per business day.
        if not settings.allow_multiple_sessions_per_day:
            prior = db.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM attendance.work_sessions
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                      AND business_date = :business_date
                      AND status IN ('CLOSED','AUTO_CLOSED')
                    LIMIT 1
                    """
                ),
                {
                    "tenant_id": actor.tenant_id,
                    "employee_id": actor.employee_id,
                    "business_date": business_date,
                },
            ).first()
            if prior is not None:
                raise AppError(
                    code="attendance.punch.multiple_sessions_not_allowed",
                    message="Multiple work sessions are not allowed for this day",
                    status_code=409,
                )

        punch_id = self._insert_punch(
            db,
            tenant_id=actor.tenant_id,
            branch_id=branch_id,
            employee_id=actor.employee_id,
            ts=now_ts,
            action="IN",
            source=source,
            created_by_user_id=ctx.user_id,
            idempotency_key=idempotency_key,
            meta=meta,
        )

        # Create the OPEN work session. Partial unique index prevents duplicates under race.
        session_id = uuid4()
        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO attendance.work_sessions (
                      id,
                      tenant_id,
                      branch_id,
                      employee_id,
                      business_date,
                      start_ts,
                      end_ts,
                      minutes,
                      start_punch_id,
                      end_punch_id,
                      status,
                      source_start,
                      source_end,
                      anomaly_code
                    ) VALUES (
                      :id,
                      :tenant_id,
                      :branch_id,
                      :employee_id,
                      :business_date,
                      :start_ts,
                      NULL,
                      0,
                      :start_punch_id,
                      NULL,
                      'OPEN',
                      :source_start,
                      NULL,
                      NULL
                    )
                    """
                ),
                {
                    "id": session_id,
                    "tenant_id": actor.tenant_id,
                    "branch_id": branch_id,
                    "employee_id": actor.employee_id,
                    "business_date": business_date,
                    "start_ts": now_ts,
                    "start_punch_id": punch_id,
                    "source_start": source,
                },
            )
        except IntegrityError as e:
            # Most likely the "one OPEN session per employee" unique index.
            raise AppError(code="attendance.punch.already_in", message="Already punched in", status_code=409) from e

        # Upsert attendance_daily minimally so /me/days and /punch-state show presence immediately.
        self._upsert_daily_on_punch_in(
            db,
            tenant_id=actor.tenant_id,
            branch_id=branch_id,
            employee_id=actor.employee_id,
            business_date=business_date,
            ts=now_ts,
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="attendance.punch.in",
            entity_type="attendance.work_session",
            entity_id=session_id,
            before=None,
            after={
                "employee_id": str(actor.employee_id),
                "branch_id": str(branch_id),
                "business_date": str(business_date),
                "source": source,
                "ts": now_ts.isoformat(),
            },
        )

        db.commit()
        return self.get_punch_state(db, ctx=ctx)

    def punch_out(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        idempotency_key: str | None,
        source: PunchSource,
        meta: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Record a punch-out and close the OPEN work session.

        Punch-out remains allowed when the branch disabled punching or the day
        became ON_LEAVE after punching in. This avoids trapping employees.
        """

        actor = _get_actor_employee_or_409(db, ctx=ctx)
        employment = resolve_current_employment(db, tenant_id=actor.tenant_id, employee_id=actor.employee_id)

        if ctx.scope.company_id is not None and ctx.scope.company_id != employment["company_id"]:
            raise AppError(code="iam.scope.mismatch", message="X-Company-Id scope mismatch", status_code=400)
        if ctx.scope.branch_id is not None and ctx.scope.branch_id != employment["branch_id"]:
            raise AppError(code="iam.scope.mismatch", message="X-Branch-Id scope mismatch", status_code=400)

        # Idempotency: allow safe retries.
        if idempotency_key:
            existing = db.execute(
                sa.text(
                    """
                    SELECT action
                    FROM attendance.punches
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                      AND idempotency_key = :idempotency_key
                    LIMIT 1
                    """
                ),
                {
                    "tenant_id": actor.tenant_id,
                    "employee_id": actor.employee_id,
                    "idempotency_key": idempotency_key,
                },
            ).first()
            if existing is not None:
                existing_action = str(existing[0])
                if existing_action == "OUT":
                    return self.get_punch_state(db, ctx=ctx)
                raise AppError(
                    code="attendance.punch.idempotency.conflict",
                    message="Idempotency key already used for a different punch action",
                    status_code=409,
                )

        # Lock the OPEN session row to make closure concurrency-safe.
        sess = db.execute(
            sa.text(
                """
                SELECT
                  id,
                  branch_id,
                  business_date,
                  start_ts,
                  start_punch_id,
                  source_start
                FROM attendance.work_sessions
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND status = 'OPEN'
                FOR UPDATE
                """
            ),
            {"tenant_id": actor.tenant_id, "employee_id": actor.employee_id},
        ).mappings().first()
        if sess is None:
            raise AppError(code="attendance.punch.not_in", message="Not currently punched in", status_code=409)

        # Even if settings disabled, we allow closing the OPEN session.
        now_ts = utcnow()
        session_branch_id = UUID(str(sess["branch_id"]))
        settings = get_or_create_punch_settings(db, tenant_id=actor.tenant_id, branch_id=session_branch_id)

        punch_id = self._insert_punch(
            db,
            tenant_id=actor.tenant_id,
            branch_id=session_branch_id,
            employee_id=actor.employee_id,
            ts=now_ts,
            action="OUT",
            source=source,
            created_by_user_id=ctx.user_id,
            idempotency_key=idempotency_key,
            meta=meta,
        )

        start_ts: datetime = sess["start_ts"]
        business_date: date = sess["business_date"]

        # Minutes are computed from timestamps; we floor to whole minutes for payroll friendliness.
        #
        # Important: business_date is defined in branch-local time. If a session crosses the
        # local midnight boundary, we clamp end_ts to midnight so the minutes belong to the
        # session's business_date. A safety worker also enforces this for truly abandoned sessions.
        tz = get_branch_timezone(db, tenant_id=actor.tenant_id, branch_id=session_branch_id)
        midnight_utc = utc_boundary_for_next_business_day(business_date, tz)

        end_ts = now_ts
        anomaly_code: str | None = None
        if end_ts > midnight_utc:
            end_ts = midnight_utc
            anomaly_code = "CROSSED_MIDNIGHT"

        max_end_ts = start_ts + timedelta(hours=max(1, int(settings.max_session_hours)))
        if end_ts > max_end_ts:
            end_ts = max_end_ts
            anomaly_code = "SESSION_TOO_LONG"

        minutes = int(max(0.0, (end_ts - start_ts).total_seconds()) // 60)

        db.execute(
            sa.text(
                """
                UPDATE attendance.work_sessions
                SET
                  end_ts = :end_ts,
                  minutes = :minutes,
                  end_punch_id = :end_punch_id,
                  status = 'CLOSED',
                  source_end = :source_end,
                  anomaly_code = :anomaly_code,
                  updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {
                "tenant_id": actor.tenant_id,
                "id": UUID(str(sess["id"])),
                "end_ts": end_ts,
                "minutes": int(minutes),
                "end_punch_id": punch_id,
                "source_end": source,
                "anomaly_code": anomaly_code,
            },
        )

        # Recompute daily rollup deterministically from CLOSED/AUTO_CLOSED sessions.
        self._rollup.recompute_daily(
            db,
            tenant_id=actor.tenant_id,
            branch_id=session_branch_id,
            employee_id=actor.employee_id,
            business_date=business_date,
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="attendance.punch.out",
            entity_type="attendance.work_session",
            entity_id=UUID(str(sess["id"])),
            before=None,
            after={
                "employee_id": str(actor.employee_id),
                "branch_id": str(sess["branch_id"]),
                "business_date": str(business_date),
                "source": source,
                "ts": now_ts.isoformat(),
                "minutes": int(minutes),
                "anomaly_code": anomaly_code,
            },
        )

        db.commit()
        return self.get_punch_state(db, ctx=ctx)

    def get_punch_state(self, db: Session, *, ctx: AuthContext) -> dict[str, Any]:
        """
        Return current punch state and effective minutes for *today*.

        We treat "today" as the branch-local business date derived from now().
        """

        actor = _get_actor_employee_or_409(db, ctx=ctx)
        employment = resolve_current_employment(db, tenant_id=actor.tenant_id, employee_id=actor.employee_id)
        branch_id = UUID(str(employment["branch_id"]))

        now_ts = utcnow()
        tz = get_branch_timezone(db, tenant_id=actor.tenant_id, branch_id=branch_id)
        business_date = business_date_for_ts(now_ts, tz)

        open_sess = db.execute(
            sa.text(
                """
                SELECT start_ts
                FROM attendance.work_sessions
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND status = 'OPEN'
                LIMIT 1
                """
            ),
            {"tenant_id": actor.tenant_id, "employee_id": actor.employee_id},
        ).first()

        daily = db.execute(
            sa.text(
                """
                SELECT total_minutes
                FROM attendance.attendance_daily
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND business_date = :day
                LIMIT 1
                """
            ),
            {"tenant_id": actor.tenant_id, "employee_id": actor.employee_id, "day": business_date},
        ).first()
        base_minutes = int(daily[0] or 0) if daily is not None else 0

        # Apply override precedence for both status and minutes.
        base_row_exists = db.execute(
            sa.text(
                """
                SELECT 1
                FROM attendance.attendance_daily
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND business_date = :day
                LIMIT 1
                """
            ),
            {"tenant_id": actor.tenant_id, "employee_id": actor.employee_id, "day": business_date},
        ).first()
        base_status = "PRESENT" if base_row_exists is not None else "ABSENT"

        overrides = (
            db.execute(
                sa.text(
                    """
                    SELECT status, payload, created_at, id
                    FROM attendance.day_overrides
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                      AND day = :day
                    ORDER BY created_at DESC, id DESC
                    """
                ),
                {"tenant_id": actor.tenant_id, "employee_id": actor.employee_id, "day": business_date},
            )
            .mappings()
            .all()
        )

        effective_status = base_status
        effective_minutes = base_minutes

        leave_found = any(str(o["status"]) == "ON_LEAVE" for o in overrides)
        if leave_found:
            effective_status = "ON_LEAVE"
            effective_minutes = 0
        else:
            corr = next((o for o in overrides if str(o["status"]) != "ON_LEAVE"), None)
            if corr is not None:
                st = str(corr["status"])
                effective_status = st

                payload = corr.get("payload") or {}
                override_minutes = None
                if isinstance(payload, dict):
                    override_minutes = payload.get("override_minutes")

                if override_minutes is not None:
                    try:
                        effective_minutes = int(override_minutes)
                    except Exception:
                        effective_minutes = base_minutes
                elif st == "ABSENT_OVERRIDE":
                    effective_minutes = 0

        return {
            "today_business_date": business_date,
            "is_punched_in": open_sess is not None,
            "open_session_started_at": open_sess[0] if open_sess is not None else None,
            "base_minutes_today": int(base_minutes),
            "effective_minutes_today": int(effective_minutes),
            "effective_status_today": effective_status,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _insert_punch(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        employee_id: UUID,
        ts: datetime,
        action: PunchAction,
        source: PunchSource,
        created_by_user_id: UUID | None,
        idempotency_key: str | None,
        meta: dict[str, Any] | None,
        source_ref_type: str | None = None,
        source_ref_id: UUID | None = None,
    ) -> UUID:
        """
        Insert a punch row and return its id.

        This is the future integration point for biometric/CCTV/import pipelines:
        they can call this helper with source=CCTV/BIOMETRIC and populate
        source_ref_* fields without changing the rest of the model.
        """

        meta_json = _json_canonical(meta) if meta is not None else None
        row = db.execute(
            sa.text(
                """
                INSERT INTO attendance.punches (
                  tenant_id,
                  branch_id,
                  employee_id,
                  ts,
                  action,
                  source,
                  source_ref_type,
                  source_ref_id,
                  created_by_user_id,
                  idempotency_key,
                  meta
                ) VALUES (
                  :tenant_id,
                  :branch_id,
                  :employee_id,
                  :ts,
                  :action,
                  :source,
                  :source_ref_type,
                  :source_ref_id,
                  :created_by_user_id,
                  :idempotency_key,
                  CAST(:meta AS jsonb)
                )
                RETURNING id
                """
            ),
            {
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "employee_id": employee_id,
                "ts": ts,
                "action": action,
                "source": source,
                "source_ref_type": source_ref_type,
                "source_ref_id": source_ref_id,
                "created_by_user_id": created_by_user_id,
                "idempotency_key": idempotency_key,
                "meta": meta_json,
            },
        ).first()
        if row is None:
            raise AppError(code="internal_error", message="Failed to insert punch", status_code=500)
        return UUID(str(row[0]))

    def _upsert_daily_on_punch_in(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        employee_id: UUID,
        business_date: date,
        ts: datetime,
    ) -> None:
        """
        Upsert a minimal daily row on punch-in.

        We do not compute minutes here; minutes are derived from CLOSED sessions.
        This upsert is purely for immediate "presence" and open-session flags.
        """

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
                  has_open_session
                ) VALUES (
                  :id,
                  :tenant_id,
                  :branch_id,
                  :business_date,
                  :employee_id,
                  :punch_in,
                  true
                )
                ON CONFLICT (branch_id, business_date, employee_id)
                DO UPDATE SET
                  punch_in = CASE
                    WHEN attendance.attendance_daily.punch_in IS NULL THEN EXCLUDED.punch_in
                    ELSE LEAST(attendance.attendance_daily.punch_in, EXCLUDED.punch_in)
                  END,
                  has_open_session = true
                WHERE attendance.attendance_daily.tenant_id = EXCLUDED.tenant_id
                """
            ),
            {
                "id": uuid4(),
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "business_date": business_date,
                "employee_id": employee_id,
                "punch_in": ts,
            },
        )
