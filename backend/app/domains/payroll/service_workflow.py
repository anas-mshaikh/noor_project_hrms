"""
Payrun workflow integration services (Milestone 9).

v1 uses Workflow Engine v1 for payrun approval:
- Submit payrun -> create workflow request type PAYRUN_APPROVAL
- Workflow terminal hook -> updates payrun status inside the workflow transaction
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.workflow.service import WorkflowService
from app.shared.types import AuthContext


class PayrunWorkflowService:
    """Submit a payrun for workflow approval (admin action)."""

    def __init__(self) -> None:
        self._workflow = WorkflowService()

    def submit_for_approval(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        payrun_id: UUID,
    ) -> dict[str, Any]:
        """
        Submit a DRAFT payrun for approval.

        Concurrency:
        - Locks the payrun row FOR UPDATE to serialize submit vs publish.

        Idempotency:
        - If already PENDING_APPROVAL and workflow_request_id is set, return it.
        """

        tenant_id = ctx.scope.tenant_id

        payrun = (
            db.execute(
                sa.text(
                    """
                    SELECT
                      pr.id,
                      pr.status,
                      pr.branch_id,
                      pr.calendar_id,
                      pr.period_id,
                      pr.workflow_request_id,
                      pr.totals_json,
                      p.period_key
                    FROM payroll.payruns pr
                    JOIN payroll.periods p ON p.id = pr.period_id AND p.tenant_id = pr.tenant_id
                    WHERE pr.tenant_id = :tenant_id
                      AND pr.id = :id
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

        # Scope hardening: hide cross-branch existence.
        if ctx.scope.branch_id is not None and UUID(str(payrun["branch_id"])) != ctx.scope.branch_id:
            raise AppError(code="payroll.payrun.not_found", message="Payrun not found", status_code=404)

        status = str(payrun["status"])
        existing_wr = payrun.get("workflow_request_id")

        if status == "PENDING_APPROVAL" and existing_wr is not None:
            return {"payrun_id": str(payrun_id), "workflow_request_id": str(existing_wr), "status": status}

        if status != "DRAFT":
            raise AppError(code="payroll.payrun.invalid_state", message="Payrun is not in DRAFT state", status_code=409)

        # Require items exist; otherwise approvals are meaningless.
        items_count = int(
            db.execute(
                sa.text(
                    """
                    SELECT count(*)
                    FROM payroll.payrun_items
                    WHERE tenant_id = :tenant_id
                      AND payrun_id = :payrun_id
                      AND status = 'INCLUDED'
                    """
                ),
                {"tenant_id": tenant_id, "payrun_id": payrun_id},
            ).scalar()
            or 0
        )
        if items_count <= 0:
            raise AppError(code="payroll.payrun.invalid_state", message="Payrun has no included items", status_code=409)

        payload = {
            "subject": "Payrun Approval",
            "period_key": str(payrun["period_key"]),
            "payrun_id": str(payrun_id),
            "branch_id": str(payrun["branch_id"]) if payrun.get("branch_id") is not None else None,
            # Avoid per-employee amounts in workflow payloads.
            "totals": {
                "included_count": (payrun.get("totals_json") or {}).get("included_count"),
                "excluded_count": (payrun.get("totals_json") or {}).get("excluded_count"),
                "currency_code": (payrun.get("totals_json") or {}).get("currency_code"),
            },
        }

        # Workflow engine requires requester_user -> requester_employee linkage.
        wr = self._workflow.create_request(
            db,
            ctx=ctx,
            request_type_code="PAYRUN_APPROVAL",
            payload=payload,
            subject_employee_id=None,
            entity_type="payroll.payrun",
            entity_id=payrun_id,
            company_id_hint=None,
            branch_id_hint=ctx.scope.branch_id,
            idempotency_key=f"payrun_approval:{payrun_id}",
            initial_comment=None,
            commit=False,
        )

        db.execute(
            sa.text(
                """
                UPDATE payroll.payruns
                SET status = 'PENDING_APPROVAL',
                    workflow_request_id = :workflow_request_id,
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": payrun_id, "workflow_request_id": wr["id"]},
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="payroll.payrun.submit",
            entity_type="payroll.payrun",
            entity_id=payrun_id,
            before=None,
            after={"workflow_request_id": str(wr["id"])},
        )

        db.commit()
        return {"payrun_id": str(payrun_id), "workflow_request_id": str(wr["id"]), "status": "PENDING_APPROVAL"}

