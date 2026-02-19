"""
Onboarding v2 bundle service (Milestone 6).

This module contains HR/admin operations for onboarding bundles:
- create an employee bundle from a template
- snapshot template tasks into employee tasks (deterministic history)
- read an employee's active bundle (HR reporting)

Assignee resolution is intentionally best-effort in v1:
- If we cannot resolve an assignee user_id, the task remains unassigned and
  notifications are skipped for that task.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.onboarding.utils import (
    enqueue_notification,
    list_employee_user_ids,
    utcnow,
)
from app.shared.types import AuthContext


class OnboardingBundleService:
    """HR-facing onboarding bundle operations."""

    def create_bundle(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        employee_id: UUID,
        template_code: str,
        branch_id: UUID,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """
        Create an ACTIVE bundle and snapshot tasks in one DB transaction.

        Concurrency:
        - The DB enforces "1 active bundle per employee" via a partial unique
          index on onboarding.employee_bundles.
        """

        tenant_id = ctx.scope.tenant_id

        emp = db.execute(
            sa.text(
                "SELECT company_id FROM hr_core.employees WHERE tenant_id = :tenant_id AND id = :id"
            ),
            {"tenant_id": tenant_id, "id": employee_id},
        ).first()
        if emp is None:
            raise AppError(
                code="hr.employee.not_found",
                message="Employee not found",
                status_code=404,
            )
        employee_company_id = UUID(str(emp[0]))

        # Scope hardening: avoid cross-company leaks for scoped HR users.
        if ctx.scope.allowed_company_ids and employee_company_id not in set(
            ctx.scope.allowed_company_ids
        ):
            raise AppError(
                code="hr.employee.not_found",
                message="Employee not found",
                status_code=404,
            )

        branch_ok = db.execute(
            sa.text(
                """
                SELECT 1
                FROM tenancy.branches
                WHERE id = :branch_id
                  AND tenant_id = :tenant_id
                  AND company_id = :company_id
                """
            ),
            {
                "branch_id": branch_id,
                "tenant_id": tenant_id,
                "company_id": employee_company_id,
            },
        ).first()
        if branch_ok is None:
            raise AppError(
                code="validation_error", message="Invalid branch_id", status_code=400
            )

        tmpl = (
            db.execute(
                sa.text(
                    """
                SELECT *
                FROM onboarding.plan_templates
                WHERE tenant_id = :tenant_id
                  AND code = :code
                  AND is_active = true
                """
                ),
                {"tenant_id": tenant_id, "code": template_code},
            )
            .mappings()
            .first()
        )
        if tmpl is None:
            raise AppError(
                code="onboarding.template.not_found",
                message="Template not found",
                status_code=404,
            )

        # Optional scope enforcement (v1): if template is scoped, it must match.
        if (
            tmpl.get("company_id") is not None
            and UUID(str(tmpl["company_id"])) != employee_company_id
        ):
            raise AppError(
                code="onboarding.template.not_found",
                message="Template not found",
                status_code=404,
            )
        if (
            tmpl.get("branch_id") is not None
            and UUID(str(tmpl["branch_id"])) != branch_id
        ):
            raise AppError(
                code="onboarding.template.not_found",
                message="Template not found",
                status_code=404,
            )

        bundle_id = uuid4()
        now = utcnow()

        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO onboarding.employee_bundles (
                      id, tenant_id, employee_id, plan_template_id, branch_id,
                      status, created_by_user_id, created_at, updated_at
                    ) VALUES (
                      :id, :tenant_id, :employee_id, :plan_template_id, :branch_id,
                      'ACTIVE', :created_by_user_id, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": bundle_id,
                    "tenant_id": tenant_id,
                    "employee_id": employee_id,
                    "plan_template_id": UUID(str(tmpl["id"])),
                    "branch_id": branch_id,
                    "created_by_user_id": ctx.user_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="onboarding.bundle.already_exists",
                message="Employee already has an active onboarding bundle",
                status_code=409,
            ) from e

        # Snapshot tasks from template.
        tmpl_tasks = (
            db.execute(
                sa.text(
                    """
                SELECT *
                FROM onboarding.plan_template_tasks
                WHERE tenant_id = :tenant_id
                  AND plan_template_id = :plan_template_id
                ORDER BY order_index ASC, id ASC
                """
                ),
                {"tenant_id": tenant_id, "plan_template_id": UUID(str(tmpl["id"]))},
            )
            .mappings()
            .all()
        )

        task_rows: list[dict[str, Any]] = []
        for t in tmpl_tasks:
            task_id = uuid4()
            due_on = None
            if t.get("due_days") is not None:
                due_on = now.date() + timedelta(days=int(t["due_days"]))

            assigned_to_user_id = self._resolve_assignee_user_id(
                db,
                tenant_id=tenant_id,
                company_id=employee_company_id,
                branch_id=branch_id,
                employee_id=employee_id,
                assignee_type=str(t["assignee_type"]),
                assignee_role_code=str(t.get("assignee_role_code"))
                if t.get("assignee_role_code")
                else None,
            )

            db.execute(
                sa.text(
                    """
                    INSERT INTO onboarding.employee_tasks (
                      id, tenant_id, bundle_id,
                      task_code, title, description,
                      task_type, required, order_index, due_on,
                      assignee_type, assignee_role_code, assigned_to_user_id,
                      status,
                      submission_payload,
                      related_document_id,
                      verification_workflow_request_id,
                      decided_at,
                      decided_by_user_id,
                      created_at, updated_at
                    ) VALUES (
                      :id, :tenant_id, :bundle_id,
                      :task_code, :title, :description,
                      :task_type, :required, :order_index, :due_on,
                      :assignee_type, :assignee_role_code, :assigned_to_user_id,
                      'PENDING',
                      NULL,
                      NULL,
                      NULL,
                      NULL,
                      NULL,
                      :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": task_id,
                    "tenant_id": tenant_id,
                    "bundle_id": bundle_id,
                    "task_code": str(t["code"]),
                    "title": str(t["title"]),
                    "description": t.get("description"),
                    "task_type": str(t["task_type"]),
                    "required": bool(t["required"]),
                    "order_index": int(t["order_index"]),
                    "due_on": due_on,
                    "assignee_type": str(t["assignee_type"]),
                    "assignee_role_code": t.get("assignee_role_code"),
                    "assigned_to_user_id": assigned_to_user_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )

            task_rows.append(
                {
                    "id": task_id,
                    "assigned_to_user_id": assigned_to_user_id,
                    "task_code": str(t["code"]),
                }
            )

        audit_svc.record(
            db,
            ctx=ctx,
            action="onboarding.bundle.create",
            entity_type="onboarding.employee_bundle",
            entity_id=bundle_id,
            before=None,
            after={
                "employee_id": str(employee_id),
                "template_code": template_code,
                "tasks_count": len(task_rows),
            },
        )

        # Notifications (idempotent via dedupe_key).
        for uid in list_employee_user_ids(db, employee_id=employee_id):
            enqueue_notification(
                db,
                tenant_id=tenant_id,
                recipient_user_id=uid,
                template_code="onboarding.bundle.created",
                dedupe_key=f"onboarding.bundle.created:{bundle_id}:{uid}",
                payload={
                    "title": "Onboarding started",
                    "body": "An onboarding bundle was created for you.",
                    "entity_type": "onboarding.employee_bundle",
                    "entity_id": str(bundle_id),
                    "action_url": "/ess/me/onboarding",
                    "correlation_id": ctx.correlation_id,
                },
            )

        for t in task_rows:
            if t["assigned_to_user_id"] is None:
                continue
            assignee_id = UUID(str(t["assigned_to_user_id"]))
            enqueue_notification(
                db,
                tenant_id=tenant_id,
                recipient_user_id=assignee_id,
                template_code="onboarding.task.assigned",
                dedupe_key=f"onboarding.task.assigned:{t['id']}:{assignee_id}",
                payload={
                    "title": "Onboarding task assigned",
                    "body": f"Task {t['task_code']} was assigned.",
                    "entity_type": "onboarding.employee_task",
                    "entity_id": str(t["id"]),
                    "action_url": "/ess/me/onboarding",
                    "correlation_id": ctx.correlation_id,
                },
            )

        db.commit()

        bundle = (
            db.execute(
                sa.text(
                    "SELECT * FROM onboarding.employee_bundles WHERE tenant_id = :tenant_id AND id = :id"
                ),
                {"tenant_id": tenant_id, "id": bundle_id},
            )
            .mappings()
            .first()
        )
        assert bundle is not None

        tasks = (
            db.execute(
                sa.text(
                    """
                SELECT *
                FROM onboarding.employee_tasks
                WHERE tenant_id = :tenant_id
                  AND bundle_id = :bundle_id
                ORDER BY order_index ASC, id ASC
                """
                ),
                {"tenant_id": tenant_id, "bundle_id": bundle_id},
            )
            .mappings()
            .all()
        )
        return dict(bundle), [dict(r) for r in tasks]

    def get_active_bundle_for_employee(
        self, db: Session, *, ctx: AuthContext, employee_id: UUID
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """HR read path: return active bundle + tasks for an employee."""

        tenant_id = ctx.scope.tenant_id
        bundle = (
            db.execute(
                sa.text(
                    """
                SELECT *
                FROM onboarding.employee_bundles
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND status = 'ACTIVE'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
                ),
                {"tenant_id": tenant_id, "employee_id": employee_id},
            )
            .mappings()
            .first()
        )
        if bundle is None:
            raise AppError(
                code="onboarding.bundle.not_found",
                message="Bundle not found",
                status_code=404,
            )

        tasks = (
            db.execute(
                sa.text(
                    """
                SELECT *
                FROM onboarding.employee_tasks
                WHERE tenant_id = :tenant_id
                  AND bundle_id = :bundle_id
                ORDER BY order_index ASC, id ASC
                """
                ),
                {"tenant_id": tenant_id, "bundle_id": UUID(str(bundle["id"]))},
            )
            .mappings()
            .all()
        )
        return dict(bundle), [dict(r) for r in tasks]

    # ------------------------------------------------------------------
    # Assignee resolution (best-effort)
    # ------------------------------------------------------------------
    def _resolve_assignee_user_id(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        company_id: UUID,
        branch_id: UUID,
        employee_id: UUID,
        assignee_type: str,
        assignee_role_code: str | None,
    ) -> UUID | None:
        """
        Resolve a single user_id for task assignment.

        v1 behavior is best-effort:
        - If we cannot resolve an assignee, assigned_to_user_id stays NULL.
        - Notifications are only emitted when a user_id is available.

        Customization placeholder:
        - Add support for multi-assignee tasks or HR queues later.
        """

        if assignee_type == "EMPLOYEE":
            rows = db.execute(
                sa.text(
                    """
                    SELECT user_id
                    FROM hr_core.employee_user_links
                    WHERE employee_id = :employee_id
                    ORDER BY created_at ASC, user_id ASC
                    LIMIT 1
                    """
                ),
                {"employee_id": employee_id},
            ).first()
            return UUID(str(rows[0])) if rows is not None else None

        if assignee_type == "MANAGER":
            mgr_emp = db.execute(
                sa.text(
                    """
                    SELECT manager_employee_id
                    FROM hr_core.v_employee_current_employment
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                    """
                ),
                {"tenant_id": tenant_id, "employee_id": employee_id},
            ).first()
            if mgr_emp is None or mgr_emp[0] is None:
                return None
            mgr_employee_id = UUID(str(mgr_emp[0]))
            mgr_user = db.execute(
                sa.text(
                    """
                    SELECT user_id
                    FROM hr_core.employee_user_links
                    WHERE employee_id = :employee_id
                    ORDER BY created_at ASC, user_id ASC
                    LIMIT 1
                    """
                ),
                {"employee_id": mgr_employee_id},
            ).first()
            return UUID(str(mgr_user[0])) if mgr_user is not None else None

        if assignee_type == "ROLE":
            if not assignee_role_code:
                return None
            row = db.execute(
                sa.text(
                    """
                    SELECT ur.user_id
                    FROM iam.user_roles ur
                    JOIN iam.roles r ON r.id = ur.role_id
                    WHERE ur.tenant_id = :tenant_id
                      AND r.code = :role_code
                      AND (ur.company_id IS NULL OR ur.company_id = :company_id)
                      AND (ur.branch_id IS NULL OR ur.branch_id = :branch_id)
                    ORDER BY ur.created_at ASC, ur.user_id ASC
                    LIMIT 1
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "role_code": assignee_role_code,
                    "company_id": company_id,
                    "branch_id": branch_id,
                },
            ).first()
            return UUID(str(row[0])) if row is not None else None

        return None
