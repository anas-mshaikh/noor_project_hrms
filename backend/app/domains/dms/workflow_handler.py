"""
Workflow hook handler for entity_type="dms.document".

This is invoked by the workflow engine when a DOCUMENT_VERIFICATION request
reaches a terminal state (approved/rejected/cancelled).

Important constraints:
- MUST be tenant-safe (always filter by tenant_id).
- MUST be idempotent (may be invoked more than once due to retries).
- MUST NOT call db.commit() (runs inside workflow transaction).
"""

from __future__ import annotations


import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.shared.types import AuthContext


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DmsDocumentWorkflowHandler:
    """
    Terminal state side-effects for DMS documents.
    """

    def on_approved(
        self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]
    ) -> None:
        tenant_id = ctx.scope.tenant_id
        document_id = _coerce_uuid(workflow_request.get("entity_id"))
        if document_id is None:
            return

        doc = (
            db.execute(
                sa.text(
                    """
                SELECT
                  id,
                  tenant_id,
                  status,
                  owner_employee_id
                FROM dms.documents
                WHERE id = :id
                  AND tenant_id = :tenant_id
                FOR UPDATE
                """
                ),
                {"id": document_id, "tenant_id": tenant_id},
            )
            .mappings()
            .first()
        )
        if doc is None:
            # Hide details from workflow engine callers; document may have been deleted.
            raise AppError(
                code="dms.document.not_found",
                message="Document not found",
                status_code=404,
            )

        if str(doc["status"]) == "VERIFIED":
            return

        before = {"status": str(doc["status"])}

        db.execute(
            sa.text(
                """
                UPDATE dms.documents
                SET status = 'VERIFIED',
                    verified_at = :verified_at,
                    verified_by_user_id = :verified_by_user_id,
                    rejected_reason = NULL,
                    updated_at = now()
                WHERE id = :id
                  AND tenant_id = :tenant_id
                """
            ),
            {
                "id": document_id,
                "tenant_id": tenant_id,
                "verified_at": _utcnow(),
                "verified_by_user_id": ctx.user_id,
            },
        )

        # Notify the owner (if they have a linked user account).
        owner_employee_id = doc.get("owner_employee_id")
        if owner_employee_id is not None:
            self._notify_owner(
                db,
                tenant_id=tenant_id,
                owner_employee_id=UUID(str(owner_employee_id)),
                template_code="dms.document.verified",
                title="Document verified",
                body="Your document was verified by HR.",
                document_id=document_id,
                correlation_id=ctx.correlation_id,
                dedupe_suffix=f"verified:{document_id}",
            )

        after = {"status": "VERIFIED"}
        audit_svc.record(
            db,
            ctx=ctx,
            action="dms.document.verified",
            entity_type="dms.document",
            entity_id=document_id,
            before=before,
            after=after,
        )

    def on_rejected(
        self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]
    ) -> None:
        tenant_id = ctx.scope.tenant_id
        document_id = _coerce_uuid(workflow_request.get("entity_id"))
        if document_id is None:
            return

        doc = (
            db.execute(
                sa.text(
                    """
                SELECT
                  id,
                  tenant_id,
                  status,
                  owner_employee_id
                FROM dms.documents
                WHERE id = :id
                  AND tenant_id = :tenant_id
                FOR UPDATE
                """
                ),
                {"id": document_id, "tenant_id": tenant_id},
            )
            .mappings()
            .first()
        )
        if doc is None:
            raise AppError(
                code="dms.document.not_found",
                message="Document not found",
                status_code=404,
            )

        if str(doc["status"]) == "REJECTED":
            return

        before = {"status": str(doc["status"])}

        rejected_reason = "Rejected via verification workflow"

        db.execute(
            sa.text(
                """
                UPDATE dms.documents
                SET status = 'REJECTED',
                    verified_at = NULL,
                    verified_by_user_id = NULL,
                    rejected_reason = :rejected_reason,
                    updated_at = now()
                WHERE id = :id
                  AND tenant_id = :tenant_id
                """
            ),
            {
                "id": document_id,
                "tenant_id": tenant_id,
                "rejected_reason": rejected_reason,
            },
        )

        owner_employee_id = doc.get("owner_employee_id")
        if owner_employee_id is not None:
            self._notify_owner(
                db,
                tenant_id=tenant_id,
                owner_employee_id=UUID(str(owner_employee_id)),
                template_code="dms.document.rejected",
                title="Document rejected",
                body="Your document was rejected by HR.",
                document_id=document_id,
                correlation_id=ctx.correlation_id,
                dedupe_suffix=f"rejected:{document_id}",
            )

        after = {"status": "REJECTED"}
        audit_svc.record(
            db,
            ctx=ctx,
            action="dms.document.rejected",
            entity_type="dms.document",
            entity_id=document_id,
            before=before,
            after=after,
        )

    def on_cancelled(
        self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]
    ) -> None:
        """
        Cancellation does not change the document lifecycle in v1.

        We clear the verification_workflow_request_id (if it matches) so HR can
        resubmit verification later.
        """

        tenant_id = ctx.scope.tenant_id
        document_id = _coerce_uuid(workflow_request.get("entity_id"))
        if document_id is None:
            return

        req_id = _coerce_uuid(workflow_request.get("id"))

        db.execute(
            sa.text(
                """
                UPDATE dms.documents
                SET verification_workflow_request_id = NULL,
                    updated_at = now()
                WHERE id = :id
                  AND tenant_id = :tenant_id
                  AND (
                    :req_id IS NULL
                    OR verification_workflow_request_id = :req_id
                  )
                """
            ),
            {"id": document_id, "tenant_id": tenant_id, "req_id": req_id},
        )

    # ------------------------------------------------------------------
    # Notification helpers
    # ------------------------------------------------------------------
    def _notify_owner(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        owner_employee_id: UUID,
        template_code: str,
        title: str,
        body: str,
        document_id: UUID,
        correlation_id: str | None,
        dedupe_suffix: str,
    ) -> None:
        """
        Enqueue one in-app notification per linked user (idempotent via dedupe_key).
        """

        user_rows = db.execute(
            sa.text(
                """
                SELECT user_id
                FROM hr_core.employee_user_links
                WHERE employee_id = :employee_id
                ORDER BY created_at ASC, user_id ASC
                """
            ),
            {"employee_id": owner_employee_id},
        ).all()
        for (user_id_raw,) in user_rows:
            user_id = UUID(str(user_id_raw))
            dedupe_key = f"dms:{template_code}:{dedupe_suffix}:{user_id}"
            payload = {
                "title": title,
                "body": body,
                "entity_type": "dms.document",
                "entity_id": str(document_id),
                "action_url": f"/dms/documents/{document_id}",
                "correlation_id": correlation_id,
            }

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
                    "recipient_user_id": user_id,
                    "template_code": template_code,
                    "payload": json.dumps(payload, default=str),
                    "dedupe_key": dedupe_key,
                },
            )


def _coerce_uuid(value) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(str(value))
    except Exception:
        return None
