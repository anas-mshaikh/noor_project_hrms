from __future__ import annotations

"""
Attendance session safety worker (Milestone 7).

Responsibilities:
- Auto-close abandoned OPEN work sessions (missing punch-out)
- Clamp sessions that cross local midnight (branch timezone)
- Recompute daily rollups (attendance.attendance_daily) deterministically
- Emit audit rows and (optional) in-app notifications via notification_outbox

Scheduling:
- v1 does not add a scheduler. Ops/cron can invoke `run_once()`.
- Tests call `run_once()` directly.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.db.session import SessionLocal
from app.domains.attendance.service_rollup import DailyRollupService
from app.domains.attendance.time_utils import (
    business_date_for_ts,
    utc_boundary_for_next_business_day,
)
from app.shared.types import AuthContext, Scope


logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json_canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _list_employee_user_ids(db: Session, *, employee_id: UUID) -> list[UUID]:
    """Return all linked user_ids for an employee (deterministic order)."""

    rows = db.execute(
        sa.text(
            """
            SELECT user_id
            FROM hr_core.employee_user_links
            WHERE employee_id = :employee_id
            ORDER BY created_at ASC, user_id ASC
            """
        ),
        {"employee_id": employee_id},
    ).all()
    return [UUID(str(r[0])) for r in rows]


def _enqueue_outbox(
    db: Session,
    *,
    tenant_id: UUID,
    recipient_user_id: UUID,
    template_code: str,
    dedupe_key: str,
    payload: dict[str, object],
) -> None:
    """
    Insert one in-app notification into workflow.notification_outbox (idempotent).
    """

    db.execute(
        sa.text(
            """
            INSERT INTO workflow.notification_outbox (
              tenant_id, channel, recipient_user_id, template_code, payload, dedupe_key
            ) VALUES (
              :tenant_id, 'IN_APP', :recipient_user_id, :template_code, CAST(:payload AS jsonb), :dedupe_key
            )
            ON CONFLICT (tenant_id, channel, dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
            """
        ),
        {
            "tenant_id": tenant_id,
            "recipient_user_id": recipient_user_id,
            "template_code": template_code,
            "payload": _json_canonical(payload),
            "dedupe_key": dedupe_key,
        },
    )


def _fallback_actor_user_id(db: Session, *, tenant_id: UUID) -> UUID | None:
    """
    Return a deterministic fallback actor user_id for audit attribution.

    In most cases, the OPEN session was created by an ESS user, and we can use
    the punch.created_by_user_id. For system-created sessions (future), we
    fall back to the first active user in the tenant.
    """

    row = db.execute(
        sa.text(
            """
            SELECT u.id
            FROM iam.user_roles ur
            JOIN iam.users u ON u.id = ur.user_id
            WHERE ur.tenant_id = :tenant_id
              AND u.status = 'ACTIVE'
              AND u.deleted_at IS NULL
            ORDER BY ur.created_at ASC, u.id ASC
            LIMIT 1
            """
        ),
        {"tenant_id": tenant_id},
    ).first()
    if row is None:
        return None
    return UUID(str(row[0]))


def _system_ctx(*, tenant_id: UUID, actor_user_id: UUID) -> AuthContext:
    """
    Build a minimal AuthContext for audit logging in a worker context.
    """

    return AuthContext(
        user_id=actor_user_id,
        email="system@local",
        status="ACTIVE",
        roles=(),
        scope=Scope(tenant_id=tenant_id, company_id=None, branch_id=None),
        permissions=frozenset(),
        correlation_id=None,
    )


@dataclass(frozen=True)
class AutoCloseResult:
    closed_count: int


def _should_auto_close(
    *,
    now_ts: datetime,
    start_ts: datetime,
    session_business_date,
    tz: ZoneInfo,
    max_session_hours: int,
) -> bool:
    """
    Decide whether an OPEN session should be auto-closed.

    Conditions:
    - Session exceeds max_session_hours
    - Branch-local business date moved beyond the session's business_date
    """

    if (now_ts - start_ts) > timedelta(hours=max(1, int(max_session_hours))):
        return True
    now_day = business_date_for_ts(now_ts, tz)
    return bool(now_day > session_business_date)


def run_once(*, now_ts: datetime | None = None, limit: int = 200) -> int:
    """
    Run a single auto-close pass.

    Returns: number of sessions closed.
    """

    if now_ts is None:
        now_ts = _utcnow()
    if now_ts.tzinfo is None:
        now_ts = now_ts.replace(tzinfo=timezone.utc)

    db = SessionLocal()
    rollup = DailyRollupService()
    closed = 0

    try:
        # Load OPEN sessions with enough context to decide closure in Python.
        rows = (
            db.execute(
                sa.text(
                    """
                    SELECT
                      ws.id,
                      ws.tenant_id,
                      ws.branch_id,
                      ws.employee_id,
                      ws.business_date,
                      ws.start_ts,
                      ws.start_punch_id,
                      p.created_by_user_id AS start_created_by_user_id,
                      COALESCE(ps.max_session_hours, 16) AS max_session_hours,
                      b.timezone AS branch_timezone
                    FROM attendance.work_sessions ws
                    JOIN tenancy.branches b
                      ON b.id = ws.branch_id
                     AND b.tenant_id = ws.tenant_id
                    LEFT JOIN attendance.punch_settings ps
                      ON ps.tenant_id = ws.tenant_id AND ps.branch_id = ws.branch_id
                    LEFT JOIN attendance.punches p
                      ON p.id = ws.start_punch_id
                     AND p.tenant_id = ws.tenant_id
                    WHERE ws.status = 'OPEN'
                    ORDER BY ws.start_ts ASC, ws.id ASC
                    LIMIT :limit
                    """
                ),
                {"limit": int(limit)},
            )
            .mappings()
            .all()
        )

        for r in rows:
            tenant_id = UUID(str(r["tenant_id"]))
            branch_id = UUID(str(r["branch_id"]))
            employee_id = UUID(str(r["employee_id"]))
            session_id = UUID(str(r["id"]))
            business_date = r["business_date"]
            start_ts: datetime = r["start_ts"]
            max_session_hours = int(r.get("max_session_hours") or 16)
            tz_name = str(r.get("branch_timezone") or "UTC")

            try:
                tz = ZoneInfo(tz_name)
            except Exception:
                tz = ZoneInfo("UTC")

            if not _should_auto_close(
                now_ts=now_ts,
                start_ts=start_ts,
                session_business_date=business_date,
                tz=tz,
                max_session_hours=max_session_hours,
            ):
                continue

            # Lock the session row before updating (concurrency-safe).
            locked = db.execute(
                sa.text(
                    """
                    SELECT id, business_date, start_ts
                    FROM attendance.work_sessions
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                      AND status = 'OPEN'
                    FOR UPDATE
                    """
                ),
                {"tenant_id": tenant_id, "id": session_id},
            ).mappings().first()
            if locked is None:
                continue

            # Clamp end_ts:
            # - Do not exceed now_ts
            # - Do not exceed max_session_hours from start
            # - Do not exceed the local midnight boundary after business_date
            midnight_utc = utc_boundary_for_next_business_day(business_date, tz)
            max_end_ts = start_ts + timedelta(hours=max(1, int(max_session_hours)))
            end_ts = min(now_ts, midnight_utc, max_end_ts)

            minutes = int(max(0.0, (end_ts - start_ts).total_seconds()) // 60)

            db.execute(
                sa.text(
                    """
                    UPDATE attendance.work_sessions
                    SET
                      end_ts = :end_ts,
                      minutes = :minutes,
                      status = 'AUTO_CLOSED',
                      source_end = 'SYSTEM',
                      anomaly_code = 'MISSING_OUT',
                      updated_at = now()
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                      AND status = 'OPEN'
                    """
                ),
                {"tenant_id": tenant_id, "id": session_id, "end_ts": end_ts, "minutes": minutes},
            )

            rollup.recompute_daily(
                db,
                tenant_id=tenant_id,
                branch_id=branch_id,
                employee_id=employee_id,
                business_date=business_date,
            )

            # Audit attribution: prefer the start punch's created_by_user_id, else fallback.
            actor_user_id = r.get("start_created_by_user_id")
            actor_uuid = UUID(str(actor_user_id)) if actor_user_id is not None else _fallback_actor_user_id(db, tenant_id=tenant_id)
            if actor_uuid is not None:
                audit_svc.record(
                    db,
                    ctx=_system_ctx(tenant_id=tenant_id, actor_user_id=actor_uuid),
                    action="attendance.session.auto_closed",
                    entity_type="attendance.work_session",
                    entity_id=session_id,
                    before=None,
                    after={
                        "employee_id": str(employee_id),
                        "branch_id": str(branch_id),
                        "business_date": str(business_date),
                        "end_ts": end_ts.isoformat(),
                        "minutes": int(minutes),
                        "anomaly_code": "MISSING_OUT",
                        "reason": "AUTO_CLOSE",
                    },
                )

            # Optional notification: notify the employee (linked user(s)) so they can review.
            for uid in _list_employee_user_ids(db, employee_id=employee_id):
                _enqueue_outbox(
                    db,
                    tenant_id=tenant_id,
                    recipient_user_id=uid,
                    template_code="attendance.session.auto_closed",
                    dedupe_key=f"attendance:auto_close:{session_id}:{uid}",
                    payload={
                        "title": "Session auto-closed",
                        "body": "An open attendance session was auto-closed due to a missing punch-out.",
                        "entity_type": "attendance.work_session",
                        "entity_id": str(session_id),
                    },
                )

            closed += 1

        db.commit()
        return int(closed)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
