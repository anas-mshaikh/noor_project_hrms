"""
Onboarding v2 template service (Milestone 6).

This module contains HR/admin operations for onboarding plan templates and
template tasks:
- list/create templates
- add tasks to a template

The bundle and ESS task flows are implemented in separate service modules.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.onboarding.utils import json_canonical, utcnow
from app.shared.types import AuthContext


class OnboardingTemplateService:
    """HR-facing onboarding template operations."""

    def list_templates(self, db: Session, *, ctx: AuthContext) -> list[dict[str, Any]]:
        """Return all templates for the tenant."""

        tenant_id = ctx.scope.tenant_id
        rows = db.execute(
            sa.text(
                """
                SELECT *
                FROM onboarding.plan_templates
                WHERE tenant_id = :tenant_id
                ORDER BY code ASC
                """
            ),
            {"tenant_id": tenant_id},
        ).mappings().all()
        return [dict(r) for r in rows]

    def create_template(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Create a new onboarding plan template (tenant-scoped)."""

        tenant_id = ctx.scope.tenant_id
        template_id = uuid4()
        now = utcnow()

        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO onboarding.plan_templates (
                      id, tenant_id, code, name, is_active,
                      company_id, branch_id, job_title_id, grade_id, org_unit_id,
                      created_by_user_id, created_at, updated_at
                    ) VALUES (
                      :id, :tenant_id, :code, :name, :is_active,
                      :company_id, :branch_id, :job_title_id, :grade_id, :org_unit_id,
                      :created_by_user_id, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": template_id,
                    "tenant_id": tenant_id,
                    "code": payload["code"],
                    "name": payload["name"],
                    "is_active": bool(payload.get("is_active", True)),
                    "company_id": payload.get("company_id"),
                    "branch_id": payload.get("branch_id"),
                    "job_title_id": payload.get("job_title_id"),
                    "grade_id": payload.get("grade_id"),
                    "org_unit_id": payload.get("org_unit_id"),
                    "created_by_user_id": ctx.user_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        except IntegrityError as e:
            db.rollback()
            # Unique (tenant_id, code) is the expected conflict.
            raise AppError(
                code="validation_error",
                message="Template code already exists",
                status_code=409,
            ) from e

        audit_svc.record(
            db,
            ctx=ctx,
            action="onboarding.template.create",
            entity_type="onboarding.plan_template",
            entity_id=template_id,
            before=None,
            after={"code": payload["code"], "name": payload["name"]},
        )
        db.commit()

        created = db.execute(
            sa.text("SELECT * FROM onboarding.plan_templates WHERE tenant_id = :tenant_id AND id = :id"),
            {"tenant_id": tenant_id, "id": template_id},
        ).mappings().first()
        assert created is not None
        return dict(created)

    def add_task(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        template_id: UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Add a task to an onboarding plan template."""

        tenant_id = ctx.scope.tenant_id

        tmpl = db.execute(
            sa.text(
                """
                SELECT id
                FROM onboarding.plan_templates
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": template_id},
        ).first()
        if tmpl is None:
            raise AppError(
                code="onboarding.template.not_found",
                message="Template not found",
                status_code=404,
            )

        task_type = str(payload["task_type"])
        if task_type == "DOCUMENT" and not payload.get("required_document_type_code"):
            raise AppError(
                code="validation_error",
                message="required_document_type_code is required for DOCUMENT tasks",
                status_code=400,
            )
        if task_type != "FORM":
            # FORM-only fields should not be stored for non-FORM tasks.
            payload["form_schema"] = None
            payload["form_profile_change_mapping"] = None

        # Defensive: mapping must be an object if provided.
        mapping = payload.get("form_profile_change_mapping")
        if mapping is not None and not isinstance(mapping, dict):
            raise AppError(
                code="validation_error",
                message="form_profile_change_mapping must be an object",
                status_code=400,
            )

        task_id = uuid4()
        now = utcnow()

        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO onboarding.plan_template_tasks (
                      id, tenant_id, plan_template_id,
                      code, title, description,
                      task_type, required, order_index, due_days,
                      assignee_type, assignee_role_code,
                      required_document_type_code, requires_document_verification,
                      form_schema, form_profile_change_mapping,
                      created_at, updated_at
                    ) VALUES (
                      :id, :tenant_id, :plan_template_id,
                      :code, :title, :description,
                      :task_type, :required, :order_index, :due_days,
                      :assignee_type, :assignee_role_code,
                      :required_document_type_code, :requires_document_verification,
                      CAST(:form_schema AS jsonb), CAST(:form_profile_change_mapping AS jsonb),
                      :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": task_id,
                    "tenant_id": tenant_id,
                    "plan_template_id": template_id,
                    "code": payload["code"],
                    "title": payload["title"],
                    "description": payload.get("description"),
                    "task_type": task_type,
                    "required": bool(payload.get("required", True)),
                    "order_index": int(payload.get("order_index", 0)),
                    "due_days": payload.get("due_days"),
                    "assignee_type": payload["assignee_type"],
                    "assignee_role_code": payload.get("assignee_role_code"),
                    "required_document_type_code": payload.get("required_document_type_code"),
                    "requires_document_verification": bool(payload.get("requires_document_verification", False)),
                    "form_schema": (
                        json_canonical(payload.get("form_schema"))
                        if payload.get("form_schema") is not None
                        else None
                    ),
                    "form_profile_change_mapping": (
                        json_canonical(mapping) if mapping is not None else None
                    ),
                    "created_at": now,
                    "updated_at": now,
                },
            )
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="validation_error",
                message="Task code already exists for this template",
                status_code=409,
            ) from e

        audit_svc.record(
            db,
            ctx=ctx,
            action="onboarding.template.task.create",
            entity_type="onboarding.plan_template",
            entity_id=template_id,
            before=None,
            after={"task_code": payload["code"], "task_type": task_type},
        )
        db.commit()

        created = db.execute(
            sa.text(
                """
                SELECT *
                FROM onboarding.plan_template_tasks
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": task_id},
        ).mappings().first()
        assert created is not None
        return dict(created)

