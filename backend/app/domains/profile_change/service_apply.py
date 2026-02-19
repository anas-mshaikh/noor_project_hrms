"""
Profile change workflow terminal side-effects (Milestone 6).

This module contains `ProfileChangeApplyService`, which is invoked from the
Workflow Engine v1 terminal hook for entity_type="hr_core.profile_change_request".

IMPORTANT:
- This code runs inside the workflow approve/reject/cancel transaction.
- It MUST NOT call `db.commit()` (workflow service owns the transaction).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.profile_change.notifications import (
    enqueue_notification,
    list_employee_user_ids,
)
from app.domains.profile_change.utils import json_canonical, utcnow
from app.shared.types import AuthContext


class ProfileChangeApplyService:
    """
    Terminal state side-effects for profile change requests.

    This is invoked inside WorkflowService's approve/reject/cancel transaction.
    It MUST NOT call db.commit().
    """

    # -----------------------------
    # Hook entrypoints
    # -----------------------------
    def on_workflow_approved(
        self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]
    ) -> None:
        self._finalize(
            db, ctx=ctx, workflow_request=workflow_request, decision="APPROVED"
        )

    def on_workflow_rejected(
        self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]
    ) -> None:
        self._finalize(
            db, ctx=ctx, workflow_request=workflow_request, decision="REJECTED"
        )

    def on_workflow_cancelled(
        self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]
    ) -> None:
        self._finalize(
            db, ctx=ctx, workflow_request=workflow_request, decision="CANCELED"
        )

    # -----------------------------
    # Internal finalization
    # -----------------------------
    def _finalize(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        workflow_request: dict[str, Any],
        decision: str,
    ) -> None:
        tenant_id = ctx.scope.tenant_id
        entity_id_raw = workflow_request.get("entity_id")
        if entity_id_raw is None:
            return

        request_id = UUID(str(entity_id_raw))

        # Lock the domain row so concurrent/retry finalizations are safe.
        row = (
            db.execute(
                sa.text(
                    """
                SELECT *
                FROM hr_core.profile_change_requests
                WHERE tenant_id = :tenant_id
                  AND id = :id
                FOR UPDATE
                """
                ),
                {"tenant_id": tenant_id, "id": request_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(
                code="hr.profile_change.not_found",
                message="Profile change request not found",
                status_code=404,
            )

        current_status = str(row["status"])
        if decision == "APPROVED" and current_status == "APPROVED":
            return
        if decision == "REJECTED" and current_status == "REJECTED":
            return
        if decision == "CANCELED" and current_status == "CANCELED":
            return

        if current_status != "PENDING":
            # The workflow engine already enforces terminal transitions, but we
            # keep a domain-level guard for safety.
            raise AppError(
                code="hr.profile_change.already_terminal",
                message="Profile change request is not pending",
                status_code=409,
            )

        before = {"status": current_status}

        employee_id = UUID(str(row["employee_id"]))
        change_set = row.get("change_set") or {}

        # APPROVED is the only transition that mutates hr_core.*.
        if decision == "APPROVED":
            self._apply_change_set(
                db, tenant_id=tenant_id, employee_id=employee_id, change_set=change_set
            )

        decided_at = utcnow()

        db.execute(
            sa.text(
                """
                UPDATE hr_core.profile_change_requests
                SET status = :status,
                    decided_at = :decided_at,
                    decided_by_user_id = :decided_by_user_id,
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {
                "status": decision,
                "decided_at": decided_at,
                "decided_by_user_id": ctx.user_id,
                "tenant_id": tenant_id,
                "id": request_id,
            },
        )

        audit_action = {
            "APPROVED": "hr.profile_change.approved",
            "REJECTED": "hr.profile_change.rejected",
            "CANCELED": "hr.profile_change.cancelled",
        }[decision]

        audit_svc.record(
            db,
            ctx=ctx,
            action=audit_action,
            entity_type="hr_core.profile_change_request",
            entity_id=request_id,
            before=before,
            after={"status": decision},
        )

        # Notify the employee (best-effort).
        template = {
            "APPROVED": "hr.profile_change.approved",
            "REJECTED": "hr.profile_change.rejected",
            "CANCELED": "hr.profile_change.cancelled",
        }[decision]
        title = {
            "APPROVED": "Profile change approved",
            "REJECTED": "Profile change rejected",
            "CANCELED": "Profile change cancelled",
        }[decision]
        body = {
            "APPROVED": "Your profile change request was approved.",
            "REJECTED": "Your profile change request was rejected.",
            "CANCELED": "Your profile change request was cancelled.",
        }[decision]

        for uid in list_employee_user_ids(db, employee_id=employee_id):
            enqueue_notification(
                db,
                tenant_id=tenant_id,
                recipient_user_id=uid,
                template_code=template,
                dedupe_key=f"hrpc:{decision.lower()}:{request_id}:{uid}",
                payload={
                    "title": title,
                    "body": body,
                    "entity_type": "hr_core.profile_change_request",
                    "entity_id": str(request_id),
                    "action_url": f"/ess/profile-change-requests/{request_id}",
                    "correlation_id": ctx.correlation_id,
                },
            )

    # ------------------------------------------------------------------
    # Apply logic (controlled mutations)
    # ------------------------------------------------------------------
    def _apply_change_set(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        employee_id: UUID,
        change_set: dict[str, Any],
    ) -> None:
        """
        Apply a normalized change_set to hr_core.* tables.

        Deterministic semantics (v1):
        - phone/address: patch hr_core.persons (replace address)
        - bank_accounts/government_ids/dependents: replace-all by delete+insert

        Customization placeholder:
        - Add additional hr_core fields/tables here as scope expands.
        """

        emp = db.execute(
            sa.text(
                """
                SELECT person_id
                FROM hr_core.employees
                WHERE tenant_id = :tenant_id
                  AND id = :employee_id
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id},
        ).first()
        if emp is None:
            raise AppError(
                code="hr.profile_change.not_found",
                message="Employee not found for profile change",
                status_code=404,
            )
        person_id = UUID(str(emp[0]))

        # Patch hr_core.persons (only keys present).
        sets: list[str] = []
        params: dict[str, Any] = {"tenant_id": tenant_id, "person_id": person_id}

        if "phone" in change_set:
            sets.append("phone = :phone")
            params["phone"] = change_set.get("phone")

        if "address" in change_set:
            # Stored as JSON object; explicit null already normalized to {} at create time.
            sets.append("address = CAST(:address AS jsonb)")
            params["address"] = json_canonical(change_set.get("address") or {})

        if sets:
            db.execute(
                sa.text(
                    f"""
                    UPDATE hr_core.persons
                    SET {", ".join(sets)},
                        updated_at = now()
                    WHERE tenant_id = :tenant_id
                      AND id = :person_id
                    """
                ),
                params,
            )

        # Replace-all bank accounts.
        if "bank_accounts" in change_set:
            accounts = change_set.get("bank_accounts") or []
            db.execute(
                sa.text(
                    """
                    DELETE FROM hr_core.employee_bank_accounts
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                    """
                ),
                {"tenant_id": tenant_id, "employee_id": employee_id},
            )
            for a in accounts:
                db.execute(
                    sa.text(
                        """
                        INSERT INTO hr_core.employee_bank_accounts (
                          id, tenant_id, employee_id,
                          iban, account_number, bank_name, is_primary
                        ) VALUES (
                          :id, :tenant_id, :employee_id,
                          :iban, :account_number, :bank_name, :is_primary
                        )
                        """
                    ),
                    {
                        "id": uuid4(),
                        "tenant_id": tenant_id,
                        "employee_id": employee_id,
                        "iban": a.get("iban"),
                        "account_number": a.get("account_number"),
                        "bank_name": a.get("bank_name"),
                        "is_primary": bool(a.get("is_primary")),
                    },
                )

        # Replace-all government IDs.
        if "government_ids" in change_set:
            ids = change_set.get("government_ids") or []
            db.execute(
                sa.text(
                    """
                    DELETE FROM hr_core.employee_government_ids
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                    """
                ),
                {"tenant_id": tenant_id, "employee_id": employee_id},
            )
            for gid in ids:
                db.execute(
                    sa.text(
                        """
                        INSERT INTO hr_core.employee_government_ids (
                          id, tenant_id, employee_id,
                          id_type, id_number,
                          issued_at, expires_at,
                          issuing_country, notes
                        ) VALUES (
                          :id, :tenant_id, :employee_id,
                          :id_type, :id_number,
                          CAST(:issued_at AS date), CAST(:expires_at AS date),
                          :issuing_country, :notes
                        )
                        """
                    ),
                    {
                        "id": uuid4(),
                        "tenant_id": tenant_id,
                        "employee_id": employee_id,
                        "id_type": gid.get("id_type"),
                        "id_number": gid.get("id_number"),
                        "issued_at": gid.get("issued_at"),
                        "expires_at": gid.get("expires_at"),
                        "issuing_country": gid.get("issuing_country"),
                        "notes": gid.get("notes"),
                    },
                )

        # Replace-all dependents.
        if "dependents" in change_set:
            deps = change_set.get("dependents") or []
            db.execute(
                sa.text(
                    """
                    DELETE FROM hr_core.employee_dependents
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                    """
                ),
                {"tenant_id": tenant_id, "employee_id": employee_id},
            )
            for d in deps:
                db.execute(
                    sa.text(
                        """
                        INSERT INTO hr_core.employee_dependents (
                          id, tenant_id, employee_id,
                          name, relationship, dob
                        ) VALUES (
                          :id, :tenant_id, :employee_id,
                          :name, :relationship, CAST(:dob AS date)
                        )
                        """
                    ),
                    {
                        "id": uuid4(),
                        "tenant_id": tenant_id,
                        "employee_id": employee_id,
                        "name": d.get("name"),
                        "relationship": d.get("relationship"),
                        "dob": d.get("dob"),
                    },
                )
