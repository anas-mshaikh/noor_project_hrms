from __future__ import annotations

"""
DMS expiry worker (Milestone 5).

Responsibilities:
1) Materialize expiry events (dms.expiry_events) idempotently for a window
2) Emit in-app notifications via workflow.notification_outbox (dedupe_key-based)

Scheduling:
- v1 does not add a scheduler; callers (cron/K8s/ops) can invoke `run_once()`.
- Tests call `run_once()` directly.
"""

import json
import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RunResult:
    events_inserted: int
    notifications_enqueued: int


def _utc_today() -> date:
    return datetime.now(timezone.utc).date()


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
            "payload": json.dumps(payload, default=str),
            "dedupe_key": dedupe_key,
        },
    )


def _upsert_events_for_window(db: Session, *, from_date: date, to_date: date) -> int:
    """
    Insert expiry events for [from_date, to_date] inclusive.

    v1 generates EXPIRING events only:
    - notify_on_date = expires_at - days_before (per rule)

    We keep the schema capable of EXPIRED events for future enhancements, but
    we intentionally avoid generating them in v1 to keep notifications simple.
    """

    rules = (
        db.execute(
            sa.text(
                """
            SELECT id, tenant_id, document_type_id, days_before
            FROM dms.expiry_rules
            WHERE is_active = true
              AND document_type_id IS NOT NULL
              AND days_before >= 0
            ORDER BY tenant_id, document_type_id, days_before
            """
            )
        )
        .mappings()
        .all()
    )

    inserted = 0

    for r in rules:
        rule_id = UUID(str(r["id"]))
        tenant_id = UUID(str(r["tenant_id"]))
        document_type_id = UUID(str(r["document_type_id"]))
        days_before = int(r["days_before"])

        # EXPIRING notifications (before expiry).
        res1 = db.execute(
            sa.text(
                """
                INSERT INTO dms.expiry_events (
                  tenant_id, document_id, rule_id, notify_on_date, event_type
                )
                SELECT
                  d.tenant_id,
                  d.id,
                  :rule_id,
                  ((d.expires_at - (:days_before * interval '1 day'))::date) AS notify_on_date,
                  'EXPIRING' AS event_type
                FROM dms.documents d
                WHERE d.tenant_id = :tenant_id
                  AND d.document_type_id = :document_type_id
                  AND d.expires_at IS NOT NULL
                  AND ((d.expires_at - (:days_before * interval '1 day'))::date) BETWEEN :from_date AND :to_date
                ON CONFLICT (tenant_id, document_id, notify_on_date, event_type)
                  WHERE notify_on_date IS NOT NULL AND event_type IS NOT NULL
                DO NOTHING
                """
            ),
            {
                "rule_id": rule_id,
                "tenant_id": tenant_id,
                "document_type_id": document_type_id,
                "days_before": days_before,
                "from_date": from_date,
                "to_date": to_date,
            },
        )
        inserted += int(res1.rowcount or 0)

    return inserted


def _emit_due_notifications(db: Session, *, run_date: date) -> int:
    """
    For events due on run_date, enqueue one in-app notification per linked user.
    """

    rows = (
        db.execute(
            sa.text(
                """
            SELECT
              ev.id AS expiry_event_id,
              ev.tenant_id,
              ev.document_id,
              ev.event_type,
              d.expires_at,
              d.owner_employee_id,
              dt.code AS document_type_code,
              dt.name AS document_type_name
            FROM dms.expiry_events ev
            JOIN dms.documents d ON d.id = ev.document_id AND d.tenant_id = ev.tenant_id
            JOIN dms.document_types dt ON dt.id = d.document_type_id
            WHERE ev.notify_on_date = :run_date
              AND ev.event_type IS NOT NULL
            ORDER BY ev.created_at ASC, ev.id ASC
            """
            ),
            {"run_date": run_date},
        )
        .mappings()
        .all()
    )

    enqueued = 0

    for r in rows:
        tenant_id = UUID(str(r["tenant_id"]))
        event_id = UUID(str(r["expiry_event_id"]))
        document_id = UUID(str(r["document_id"]))
        event_type = str(r["event_type"] or "")
        expires_at = r.get("expires_at")
        owner_employee_id = r.get("owner_employee_id")

        if owner_employee_id is None:
            continue

        # Resolve recipients (ESS user(s) linked to employee).
        users = db.execute(
            sa.text(
                """
                SELECT user_id
                FROM hr_core.employee_user_links
                WHERE employee_id = :employee_id
                ORDER BY created_at ASC, user_id ASC
                """
            ),
            {"employee_id": UUID(str(owner_employee_id))},
        ).all()
        if not users:
            continue

        doc_type_code = str(r.get("document_type_code") or "DOCUMENT")
        doc_type_name = str(r.get("document_type_name") or doc_type_code)

        if event_type == "EXPIRED":
            template_code = "dms.document.expired"
            title = "Document expired"
            body = f"Your {doc_type_name} document has expired."
        else:
            template_code = "dms.document.expiring"
            title = "Document expiring"
            if expires_at is not None:
                days_left = int((expires_at - run_date).days)
                body = f"Your {doc_type_name} document expires on {expires_at} ({days_left} days left)."
            else:
                body = f"Your {doc_type_name} document is expiring soon."

        for (user_id_raw,) in users:
            user_id = UUID(str(user_id_raw))
            dedupe_key = f"dms:{event_type}:{event_id}:{user_id}"
            _enqueue_outbox(
                db,
                tenant_id=tenant_id,
                recipient_user_id=user_id,
                template_code=template_code,
                dedupe_key=dedupe_key,
                payload={
                    "title": title,
                    "body": body,
                    "entity_type": "dms.document",
                    "entity_id": str(document_id),
                    "action_url": f"/dms/documents/{document_id}",
                    # Worker-produced notifications do not have request correlation IDs.
                    "correlation_id": "dms_expiry_worker",
                    "document_type_code": doc_type_code,
                    "expires_at": str(expires_at) if expires_at is not None else None,
                    "event_type": event_type,
                },
            )
            enqueued += 1

    return enqueued


def run_once(*, lookahead_days: int = 60, run_date: date | None = None) -> RunResult:
    """
    Run one expiry scan + notification emission pass.

    Idempotency:
    - expiry_events uses a unique index on (tenant_id, document_id, notify_on_date, event_type)
    - notification_outbox uses dedupe_key (unique per tenant/channel)
    """

    if run_date is None:
        run_date = _utc_today()

    from_date = run_date
    to_date = run_date + timedelta(days=int(lookahead_days))

    db = SessionLocal()
    try:
        events_inserted = _upsert_events_for_window(
            db, from_date=from_date, to_date=to_date
        )
        notifications_enqueued = _emit_due_notifications(db, run_date=run_date)
        db.commit()
        return RunResult(
            events_inserted=events_inserted,
            notifications_enqueued=notifications_enqueued,
        )
    except Exception:
        db.rollback()
        logger.exception("dms_expiry_worker failed run_date=%s", run_date)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    res = run_once()
    logger.info(
        "dms_expiry_worker done events_inserted=%s notifications_enqueued=%s",
        res.events_inserted,
        res.notifications_enqueued,
    )
