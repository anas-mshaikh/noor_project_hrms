"""
Onboarding v2 shared utilities (Milestone 6).

This module contains small helper functions shared across onboarding services:
- UTC timestamp helper
- Canonical JSON serialization for JSONB writes and idempotency comparisons
- ESS actor/employee resolution (409 ess.not_linked)
- Notification outbox inserts (idempotent by dedupe_key)

Keeping these helpers in a dedicated module prevents cross-import cycles between
template, bundle, and task service modules.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.shared.types import AuthContext


def utcnow() -> datetime:
    """Return the current UTC timestamp."""

    return datetime.now(timezone.utc)


def json_canonical(value: Any) -> str:
    """
    Serialize a Python value into a stable JSON string.

    We use this to write JSONB parameters consistently and to perform stable
    idempotency comparisons. UUIDs/dates are stringified via `default=str`.
    """

    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


@dataclass(frozen=True)
class ActorEmployee:
    """Resolved ESS actor employee linkage."""

    employee_id: UUID
    tenant_id: UUID
    company_id: UUID


def get_actor_employee_or_409(db: Session, *, ctx: AuthContext) -> ActorEmployee:
    """
    Resolve the ESS employee linked to the current user.

    This mirrors other domains (leave/attendance/profile-change):
    - if not linked -> 409 ess.not_linked
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
        raise AppError(
            code="ess.not_linked",
            message="User is not linked to an employee",
            status_code=409,
        )
    employee_id, company_id = row
    return ActorEmployee(
        employee_id=UUID(str(employee_id)),
        tenant_id=tenant_id,
        company_id=UUID(str(company_id)),
    )


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

    The delivery pipeline is:
    `workflow.notification_outbox` -> worker -> `workflow.notifications`.
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
