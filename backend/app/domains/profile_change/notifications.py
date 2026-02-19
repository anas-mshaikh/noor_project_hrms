"""
Profile change notifications helper (Milestone 6).

Profile change uses the existing notification pipeline:
`workflow.notification_outbox` -> worker -> `workflow.notifications`.

This module centralizes outbox inserts and employee recipient resolution so both
the API-facing service and the workflow hook apply service behave consistently.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.domains.profile_change.utils import json_canonical


def list_employee_user_ids(db: Session, *, employee_id: UUID) -> list[UUID]:
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


def enqueue_notification(
    db: Session,
    *,
    tenant_id: UUID,
    recipient_user_id: UUID,
    template_code: str,
    dedupe_key: str,
    payload: dict[str, Any],
) -> None:
    """
    Insert an in-app notification outbox row (idempotent by dedupe_key).

    We insert directly (instead of calling WorkflowService internal helpers) to
    keep this domain decoupled from workflow internals.
    """

    db.execute(
        sa.text(
            """
            INSERT INTO workflow.notification_outbox (
              tenant_id, channel, recipient_user_id, template_code, payload, dedupe_key
            ) VALUES (
              :tenant_id, 'IN_APP', :recipient_user_id, :template_code,
              CAST(:payload AS jsonb), :dedupe_key
            )
            ON CONFLICT (tenant_id, channel, dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
            """
        ),
        {
            "tenant_id": tenant_id,
            "recipient_user_id": recipient_user_id,
            "template_code": template_code,
            "payload": json_canonical(payload),
            "dedupe_key": dedupe_key,
        },
    )
