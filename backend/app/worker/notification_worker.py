from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.session import SessionLocal


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ConsumeResult:
    processed: int
    failed: int


MAX_ATTEMPTS = 5
POLL_INTERVAL_SEC = 2.0
RETRY_BASE_SEC = 5.0
RETRY_MAX_SEC = 60.0


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_payload(payload) -> dict:
    if payload is None:
        return {}
    if isinstance(payload, dict):
        return payload
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception:
            return {"raw": payload}
    return {"raw": str(payload)}


def _coerce_uuid(value) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except Exception:
        return None


def consume_outbox_batch(db: Session, *, limit: int = 100) -> ConsumeResult:
    """
    Convert workflow.notification_outbox rows (PENDING/IN_APP) into
    workflow.notifications rows.

    Concurrency:
    - Uses SELECT ... FOR UPDATE SKIP LOCKED to allow multiple workers.
    """

    now = _utcnow()

    rows = db.execute(
        sa.text(
            """
            SELECT
              id,
              tenant_id,
              recipient_user_id,
              template_code,
              payload,
              attempts,
              created_at
            FROM workflow.notification_outbox
            WHERE channel = 'IN_APP'
              AND status = 'PENDING'
              AND (next_retry_at IS NULL OR next_retry_at <= now())
            ORDER BY created_at ASC, id ASC
            FOR UPDATE SKIP LOCKED
            LIMIT :limit
            """
        ),
        {"limit": int(limit)},
    ).mappings().all()

    processed = 0
    failed = 0

    for r in rows:
        outbox_id: UUID = r["id"]
        tenant_id: UUID = r["tenant_id"]
        recipient_user_id: UUID = r["recipient_user_id"]
        template_code: str = str(r["template_code"])
        attempts: int = int(r["attempts"] or 0)
        created_at: datetime = r["created_at"]

        payload = _parse_payload(r["payload"])
        correlation_id = payload.get("correlation_id")

        try:
            title = str(payload.get("title") or template_code)
            body = str(payload.get("body") or "")
            entity_type = payload.get("entity_type")
            entity_id = _coerce_uuid(payload.get("entity_id"))
            action_url = payload.get("action_url")

            db.execute(
                sa.text(
                    """
                    INSERT INTO workflow.notifications (
                      tenant_id,
                      recipient_user_id,
                      outbox_id,
                      type,
                      title,
                      body,
                      entity_type,
                      entity_id,
                      action_url,
                      payload,
                      created_at
                    ) VALUES (
                      :tenant_id,
                      :recipient_user_id,
                      :outbox_id,
                      :type,
                      :title,
                      :body,
                      :entity_type,
                      :entity_id,
                      :action_url,
                      CAST(:payload AS jsonb),
                      :created_at
                    )
                    ON CONFLICT (outbox_id) DO NOTHING
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "recipient_user_id": recipient_user_id,
                    "outbox_id": outbox_id,
                    "type": template_code,
                    "title": title,
                    "body": body,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "action_url": action_url,
                    "payload": json.dumps(payload, default=str),
                    "created_at": created_at,
                },
            )

            db.execute(
                sa.text(
                    """
                    UPDATE workflow.notification_outbox
                    SET status = 'SENT',
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": outbox_id},
            )
            processed += 1
        except Exception:
            failed += 1
            next_attempts = attempts + 1
            if next_attempts >= MAX_ATTEMPTS:
                next_status = "FAILED"
                next_retry_at = None
            else:
                next_status = "PENDING"
                delay = min(RETRY_BASE_SEC * (2 ** (next_attempts - 1)), RETRY_MAX_SEC)
                next_retry_at = now + timedelta(seconds=float(delay))

            db.execute(
                sa.text(
                    """
                    UPDATE workflow.notification_outbox
                    SET attempts = :attempts,
                        next_retry_at = :next_retry_at,
                        status = :status,
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {
                    "id": outbox_id,
                    "attempts": int(next_attempts),
                    "next_retry_at": next_retry_at,
                    "status": next_status,
                },
            )

            logger.exception(
                "notification_outbox consume failed outbox_id=%s tenant_id=%s user_id=%s attempts=%s correlation_id=%s",
                outbox_id,
                tenant_id,
                recipient_user_id,
                next_attempts,
                correlation_id,
            )

    return ConsumeResult(processed=processed, failed=failed)


def consume_once(*, limit: int = 100) -> ConsumeResult:
    db = SessionLocal()
    try:
        result = consume_outbox_batch(db, limit=limit)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    logger.info("notification worker started")
    while True:
        try:
            result = consume_once(limit=100)
            if result.processed == 0:
                time.sleep(POLL_INTERVAL_SEC)
        except Exception:
            logger.exception("notification worker loop error")
            time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()

