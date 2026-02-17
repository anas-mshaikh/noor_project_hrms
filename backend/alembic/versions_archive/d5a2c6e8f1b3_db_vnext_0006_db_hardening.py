"""DB vNext (0006): hardening (constraints, indexes, helper views).

Revision ID: d5a2c6e8f1b3
Revises: c4e1b3f7a9d2
Create Date: 2026-01-30

This migration adds enterprise-grade guardrails and query helpers:
- Status CHECK constraints on core vNext tables
- Critical indexes for workflow inbox/list queries
- updated_at triggers for selected module tables (HR schema)
- Helper views for common backend queries
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "d5a2c6e8f1b3"
down_revision = "c4e1b3f7a9d2"
branch_labels = None
depends_on = None


def _assert_updated_at_fn(conn) -> None:
    fn = conn.execute(sa.text("SELECT to_regprocedure('public.set_updated_at()')")).scalar()
    if fn is None:
        raise RuntimeError("Missing required function public.set_updated_at(); run DB vNext 0001 first.")


def _create_updated_at_trigger(schema: str, table: str) -> None:
    # Make this idempotent for dev DBs.
    op.execute(f"DROP TRIGGER IF EXISTS trg_set_updated_at_{schema}_{table} ON {schema}.{table}")
    op.execute(
        f"""
        CREATE TRIGGER trg_set_updated_at_{schema}_{table}
        BEFORE UPDATE ON {schema}.{table}
        FOR EACH ROW
        EXECUTE FUNCTION public.set_updated_at();
        """
    )


def upgrade() -> None:
    conn = op.get_bind()
    _assert_updated_at_fn(conn)

    # ------------------------------------------------------------------
    # 1) Critical indexes
    # ------------------------------------------------------------------
    # workflow.requests: list by status/type ordered by created_at (inbox/list pages).
    op.execute("DROP INDEX IF EXISTS workflow.ix_requests_tenant_status_type")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_requests_tenant_status_type_created_at
        ON workflow.requests (tenant_id, status, request_type_id, created_at DESC)
        """
    )

    # workflow.request_steps: approver inbox queries (pending approvals).
    # Keep existing composite index, but add a partial index for the common case.
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_request_steps_approver_pending
        ON workflow.request_steps (approver_user_id)
        WHERE decision IS NULL
        """
    )

    # hr_core.employees already has a UNIQUE constraint on (company_id, employee_code),
    # which creates a backing index. No extra index needed here.

    # dms.documents already has a partial index on (tenant_id, expires_at) where expires_at IS NOT NULL.

    # ------------------------------------------------------------------
    # 2) Status constraints (CHECK)
    # ------------------------------------------------------------------
    # tenancy.tenants.status
    op.create_check_constraint(
        "ck_tenancy_tenants_status",
        "tenants",
        "status IN ('ACTIVE','INACTIVE','SUSPENDED')",
        schema="tenancy",
    )
    # iam.users.status
    op.create_check_constraint(
        "ck_iam_users_status",
        "users",
        "status IN ('ACTIVE','DISABLED')",
        schema="iam",
    )
    # hr_core.employees.status
    op.create_check_constraint(
        "ck_hr_core_employees_status",
        "employees",
        "status IN ('ACTIVE','INACTIVE','TERMINATED')",
        schema="hr_core",
    )
    # workflow.requests.status (lowercase in vNext schema)
    op.create_check_constraint(
        "ck_workflow_requests_status",
        "requests",
        "status IN ('draft','submitted','approved','rejected','cancelled')",
        schema="workflow",
    )
    # dms.documents.status
    op.create_check_constraint(
        "ck_dms_documents_status",
        "documents",
        "status IN ('ACTIVE','ARCHIVED')",
        schema="dms",
    )

    # ------------------------------------------------------------------
    # 3) updated_at triggers for selected module tables (HR schema)
    # ------------------------------------------------------------------
    # These tables are mutated frequently by the HR APIs and benefit from a
    # consistent updated_at contract.
    for table in (
        "hr_openings",
        "hr_resumes",
        "hr_resume_views",
        "hr_applications",
        "hr_onboarding_plans",
        "hr_onboarding_tasks",
    ):
        if (
            conn.execute(sa.text("SELECT to_regclass(:fqtn)"), {"fqtn": f"hr.{table}"}).scalar()
            is None
        ):
            continue
        _create_updated_at_trigger("hr", table)

    # ------------------------------------------------------------------
    # 4) Helper views (optional but valuable)
    # ------------------------------------------------------------------
    op.execute(
        """
        CREATE OR REPLACE VIEW hr_core.v_employee_current_employment AS
        SELECT
          e.id AS employee_id,
          e.tenant_id,
          e.company_id,
          e.person_id,
          e.employee_code,
          e.status,
          e.join_date,
          e.termination_date,
          e.created_at,
          e.updated_at,
          ee.branch_id,
          ee.org_unit_id,
          ee.job_title_id,
          ee.grade_id,
          ee.manager_employee_id,
          ee.start_date,
          ee.end_date,
          ee.is_primary
        FROM hr_core.employees e
        JOIN LATERAL (
          SELECT ee_inner.*
          FROM hr_core.employee_employment ee_inner
          WHERE ee_inner.employee_id = e.id
            AND ee_inner.end_date IS NULL
          ORDER BY ee_inner.is_primary DESC, ee_inner.start_date DESC
          LIMIT 1
        ) ee ON TRUE
        """
    )

    op.execute(
        """
        CREATE OR REPLACE VIEW workflow.v_pending_approvals AS
        SELECT
          r.id AS request_id,
          r.tenant_id,
          r.company_id,
          r.branch_id,
          r.request_type_id,
          r.workflow_definition_id,
          r.requester_employee_id,
          r.subject,
          r.status,
          r.current_step,
          r.created_at,
          s.id AS request_step_id,
          s.step_order,
          s.approver_user_id
        FROM workflow.requests r
        JOIN workflow.request_steps s ON s.request_id = r.id
        WHERE s.decision IS NULL
        """
    )


def downgrade() -> None:
    # Best-effort in dev; this migration is hardening-only.
    op.execute("DROP VIEW IF EXISTS workflow.v_pending_approvals")
    op.execute("DROP VIEW IF EXISTS hr_core.v_employee_current_employment")

    op.execute("DROP INDEX IF EXISTS workflow.ix_request_steps_approver_pending")
    op.execute("DROP INDEX IF EXISTS workflow.ix_requests_tenant_status_type_created_at")

    for constraint, schema, table in (
        ("ck_dms_documents_status", "dms", "documents"),
        ("ck_workflow_requests_status", "workflow", "requests"),
        ("ck_hr_core_employees_status", "hr_core", "employees"),
        ("ck_iam_users_status", "iam", "users"),
        ("ck_tenancy_tenants_status", "tenancy", "tenants"),
    ):
        op.drop_constraint(constraint, table, type_="check", schema=schema)
