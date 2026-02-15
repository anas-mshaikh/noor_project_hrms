from __future__ import annotations

import json
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.shared.types import AuthContext


def record(
    db: Session,
    *,
    ctx: AuthContext,
    action: str,
    entity_type: str,
    entity_id: UUID | None,
    before: dict | None = None,
    after: dict | None = None,
) -> UUID:
    """
    Insert an audit row (part of the current DB transaction).

    This is intentionally lightweight for Milestone 1: we store a simple
    {before, after} payload and rely on correlation_id for traceability.
    """

    audit_id = uuid4()
    diff = {"before": before, "after": after}

    db.execute(
        sa.text(
            """
            INSERT INTO audit.audit_log (
              id, tenant_id, actor_user_id,
              action, entity_type, entity_id,
              diff_json, correlation_id
            ) VALUES (
              :id, :tenant_id, :actor_user_id,
              :action, :entity_type, :entity_id,
              CAST(:diff_json AS jsonb), :correlation_id
            )
            """
        ),
        {
            "id": audit_id,
            "tenant_id": ctx.scope.tenant_id,
            "actor_user_id": ctx.user_id,
            "action": action,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "diff_json": json.dumps(diff, default=str),
            "correlation_id": ctx.correlation_id,
        },
    )

    return audit_id

