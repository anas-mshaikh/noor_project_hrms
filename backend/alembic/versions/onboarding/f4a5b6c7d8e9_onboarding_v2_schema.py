"""Onboarding v2: templates, bundles, and tasks (Milestone 6).

Revision ID: f4a5b6c7d8e9
Revises: e3f4a5b6c7d8
Create Date: 2026-02-19

This migration creates a new schema `onboarding` that supports:
- HR-defined plan templates + template tasks
- Employee-specific bundles (instantiated from a template)
- Snapshot employee tasks (immutable "shape"; status transitions tracked on row)

Design notes:
- We intentionally snapshot only the fields required for v1 UX. For additional
  per-task metadata, v2 joins back to plan_template_tasks by (plan_template_id,
  task_code). This is safe because v1 does not support template edits.
- All tables include tenant_id and enforce tenant isolation explicitly.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as psql


# revision identifiers, used by Alembic.
revision = "f4a5b6c7d8e9"
down_revision = "e3f4a5b6c7d8"
branch_labels = None
depends_on = None


def _create_updated_at_trigger(schema: str, table: str) -> None:
    """Attach the repo-standard updated_at trigger to a table."""

    op.execute(
        sa.text(
            f"""
            CREATE TRIGGER trg_set_updated_at_{schema}_{table}
            BEFORE UPDATE ON {schema}.{table}
            FOR EACH ROW
            EXECUTE FUNCTION public.set_updated_at();
            """
        )
    )


def upgrade() -> None:
    """Apply schema changes."""

    conn = op.get_bind()
    fn = conn.execute(
        sa.text("SELECT to_regprocedure('public.set_updated_at()')")
    ).scalar()
    if fn is None:
        raise RuntimeError(
            "Missing required function public.set_updated_at(); run baseline first."
        )

    op.execute("CREATE SCHEMA IF NOT EXISTS onboarding")

    # ------------------------------------------------------------------
    # onboarding.plan_templates
    # ------------------------------------------------------------------
    op.create_table(
        "plan_templates",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        # Scope filters (nullable in v1; resolved by HR when creating bundles).
        sa.Column("company_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("job_title_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("grade_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("org_unit_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "tenant_id", "code", name="uq_onboarding_plan_templates_tenant_code"
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_onboarding_plan_templates_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_onboarding_plan_templates_company_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_onboarding_plan_templates_branch_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["job_title_id"],
            ["tenancy.job_titles.id"],
            name="fk_onboarding_plan_templates_job_title_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["grade_id"],
            ["tenancy.grades.id"],
            name="fk_onboarding_plan_templates_grade_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["org_unit_id"],
            ["tenancy.org_units.id"],
            name="fk_onboarding_plan_templates_org_unit_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["iam.users.id"],
            name="fk_onboarding_plan_templates_created_by_user_id",
            ondelete="RESTRICT",
        ),
        schema="onboarding",
    )
    op.create_index(
        "ix_onboarding_plan_templates_tenant_code",
        "plan_templates",
        ["tenant_id", "code"],
        unique=False,
        schema="onboarding",
    )
    _create_updated_at_trigger("onboarding", "plan_templates")

    # ------------------------------------------------------------------
    # onboarding.plan_template_tasks
    # ------------------------------------------------------------------
    op.create_table(
        "plan_template_tasks",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_template_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column(
            "required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("due_days", sa.Integer(), nullable=True),
        sa.Column("assignee_type", sa.Text(), nullable=False),
        sa.Column("assignee_role_code", sa.Text(), nullable=True),
        sa.Column("required_document_type_code", sa.Text(), nullable=True),
        sa.Column(
            "requires_document_verification",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("form_schema", psql.JSONB(), nullable=True),
        sa.Column("form_profile_change_mapping", psql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "task_type in ('DOCUMENT','FORM','ACK')",
            name="ck_onboarding_plan_template_tasks_task_type",
        ),
        sa.CheckConstraint(
            "assignee_type in ('EMPLOYEE','MANAGER','ROLE')",
            name="ck_onboarding_plan_template_tasks_assignee_type",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "plan_template_id",
            "code",
            name="uq_onboarding_plan_template_tasks_tenant_template_code",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_onboarding_plan_template_tasks_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_template_id"],
            ["onboarding.plan_templates.id"],
            name="fk_onboarding_plan_template_tasks_plan_template_id",
            ondelete="CASCADE",
        ),
        schema="onboarding",
    )
    op.create_index(
        "ix_onboarding_plan_template_tasks_template_order",
        "plan_template_tasks",
        ["tenant_id", "plan_template_id", "order_index"],
        unique=False,
        schema="onboarding",
    )
    _create_updated_at_trigger("onboarding", "plan_template_tasks")

    # ------------------------------------------------------------------
    # onboarding.employee_bundles
    # ------------------------------------------------------------------
    op.create_table(
        "employee_bundles",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan_template_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'ACTIVE'"),
        ),
        sa.Column("created_by_user_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status in ('ACTIVE','COMPLETED','CANCELED')",
            name="ck_onboarding_employee_bundles_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_onboarding_employee_bundles_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_onboarding_employee_bundles_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["plan_template_id"],
            ["onboarding.plan_templates.id"],
            name="fk_onboarding_employee_bundles_plan_template_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_onboarding_employee_bundles_branch_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["iam.users.id"],
            name="fk_onboarding_employee_bundles_created_by_user_id",
            ondelete="RESTRICT",
        ),
        schema="onboarding",
    )
    op.create_index(
        "ix_onboarding_employee_bundles_employee",
        "employee_bundles",
        ["tenant_id", "employee_id"],
        unique=False,
        schema="onboarding",
    )
    op.create_index(
        "uq_onboarding_employee_bundles_active_employee",
        "employee_bundles",
        ["tenant_id", "employee_id"],
        unique=True,
        schema="onboarding",
        postgresql_where=sa.text("status = 'ACTIVE'"),
    )
    _create_updated_at_trigger("onboarding", "employee_bundles")

    # ------------------------------------------------------------------
    # onboarding.employee_tasks
    # ------------------------------------------------------------------
    op.create_table(
        "employee_tasks",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("bundle_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("task_code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("task_type", sa.Text(), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("due_on", sa.Date(), nullable=True),
        sa.Column("assignee_type", sa.Text(), nullable=False),
        sa.Column("assignee_role_code", sa.Text(), nullable=True),
        sa.Column("assigned_to_user_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("submission_payload", psql.JSONB(), nullable=True),
        sa.Column("related_document_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "verification_workflow_request_id", psql.UUID(as_uuid=True), nullable=True
        ),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status in ('PENDING','SUBMITTED','APPROVED','REJECTED','SKIPPED')",
            name="ck_onboarding_employee_tasks_status",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "bundle_id",
            "task_code",
            name="uq_onboarding_employee_tasks_tenant_bundle_task_code",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_onboarding_employee_tasks_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["bundle_id"],
            ["onboarding.employee_bundles.id"],
            name="fk_onboarding_employee_tasks_bundle_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["assigned_to_user_id"],
            ["iam.users.id"],
            name="fk_onboarding_employee_tasks_assigned_to_user_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["related_document_id"],
            ["dms.documents.id"],
            name="fk_onboarding_employee_tasks_related_document_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["verification_workflow_request_id"],
            ["workflow.requests.id"],
            name="fk_onboarding_employee_tasks_verification_workflow_request_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["iam.users.id"],
            name="fk_onboarding_employee_tasks_decided_by_user_id",
            ondelete="SET NULL",
        ),
        schema="onboarding",
    )
    op.create_index(
        "ix_onboarding_employee_tasks_bundle_order",
        "employee_tasks",
        ["tenant_id", "bundle_id", "order_index"],
        unique=False,
        schema="onboarding",
    )
    op.create_index(
        "ix_onboarding_employee_tasks_assigned_status",
        "employee_tasks",
        ["tenant_id", "assigned_to_user_id", "status"],
        unique=False,
        schema="onboarding",
    )
    _create_updated_at_trigger("onboarding", "employee_tasks")


def downgrade() -> None:
    """Downgrade schema changes."""

    op.drop_index(
        "ix_onboarding_employee_tasks_assigned_status",
        table_name="employee_tasks",
        schema="onboarding",
    )
    op.drop_index(
        "ix_onboarding_employee_tasks_bundle_order",
        table_name="employee_tasks",
        schema="onboarding",
    )
    op.drop_table("employee_tasks", schema="onboarding")

    op.drop_index(
        "uq_onboarding_employee_bundles_active_employee",
        table_name="employee_bundles",
        schema="onboarding",
    )
    op.drop_index(
        "ix_onboarding_employee_bundles_employee",
        table_name="employee_bundles",
        schema="onboarding",
    )
    op.drop_table("employee_bundles", schema="onboarding")

    op.drop_index(
        "ix_onboarding_plan_template_tasks_template_order",
        table_name="plan_template_tasks",
        schema="onboarding",
    )
    op.drop_table("plan_template_tasks", schema="onboarding")

    op.drop_index(
        "ix_onboarding_plan_templates_tenant_code",
        table_name="plan_templates",
        schema="onboarding",
    )
    op.drop_table("plan_templates", schema="onboarding")

    op.execute("DROP SCHEMA IF EXISTS onboarding")
