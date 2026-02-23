"""
Workflow hook adapter for payruns (Milestone 9).

This module connects Workflow Engine v1 terminal transitions to payrun status
updates inside the same DB transaction.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.shared.types import AuthContext


class PayrunWorkflowHandler:
    """
    Workflow entity handler for entity_type="payroll.payrun".

    NOTE:
    - Must not call db.commit(); workflow engine owns the transaction.
    - Must be idempotent (may be invoked multiple times due to retries).
    """

    def on_approved(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        self._transition(db, ctx=ctx, workflow_request=workflow_request, decision="APPROVED")

    def on_rejected(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        self._transition(db, ctx=ctx, workflow_request=workflow_request, decision="REJECTED")

    def on_cancelled(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        # v1 doesn't expose payrun cancel flows; keep a safe no-op.
        return

    def _transition(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        workflow_request: dict[str, Any],
        decision: str,
    ) -> None:
        tenant_id = ctx.scope.tenant_id
        entity_id = workflow_request.get("entity_id")
        if entity_id is None:
            return
        payrun_id = UUID(str(entity_id))

        payrun = (
            db.execute(
                sa.text(
                    """
                    SELECT id, status, workflow_request_id
                    FROM payroll.payruns
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                    FOR UPDATE
                    """
                ),
                {"tenant_id": tenant_id, "id": payrun_id},
            )
            .mappings()
            .first()
        )
        if payrun is None:
            raise AppError(code="payroll.payrun.not_found", message="Payrun not found", status_code=404)

        status = str(payrun["status"])

        if decision == "APPROVED":
            # Idempotency: if already terminal, no-op.
            if status in ("APPROVED", "PUBLISHED"):
                return
            if status != "PENDING_APPROVAL":
                return

            db.execute(
                sa.text(
                    """
                    UPDATE payroll.payruns
                    SET status = 'APPROVED',
                        updated_at = now()
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                    """
                ),
                {"tenant_id": tenant_id, "id": payrun_id},
            )

            audit_svc.record(
                db,
                ctx=ctx,
                action="payroll.payrun.approved",
                entity_type="payroll.payrun",
                entity_id=payrun_id,
                before={"status": status},
                after={"status": "APPROVED"},
            )
            return

        if decision == "REJECTED":
            if status == "DRAFT":
                return
            if status == "PUBLISHED":
                # Defensive: do not revert published payruns.
                return
            if status != "PENDING_APPROVAL":
                return

            db.execute(
                sa.text(
                    """
                    UPDATE payroll.payruns
                    SET status = 'DRAFT',
                        workflow_request_id = NULL,
                        updated_at = now()
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                    """
                ),
                {"tenant_id": tenant_id, "id": payrun_id},
            )

            audit_svc.record(
                db,
                ctx=ctx,
                action="payroll.payrun.rejected",
                entity_type="payroll.payrun",
                entity_id=payrun_id,
                before={"status": status},
                after={"status": "DRAFT"},
            )
            return

