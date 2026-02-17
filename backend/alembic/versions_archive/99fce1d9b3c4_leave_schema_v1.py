"""Leave v1: create leave schema and core tables.

Revision ID: 99fce1d9b3c4
Revises: 1c9f189bf9d2
Create Date: 2026-02-16

Milestone 3 introduces a first-class Leave Management module (schema `leave`)
integrated with the workflow engine. Tables are tenant-scoped and designed for
reporting without reading workflow payload JSON.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "99fce1d9b3c4"
down_revision = "1c9f189bf9d2"
branch_labels = None
depends_on = None


def _create_updated_at_trigger(schema: str, table: str) -> None:
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
    conn = op.get_bind()
    fn = conn.execute(sa.text("SELECT to_regprocedure('public.set_updated_at()')")).scalar()
    if fn is None:
        raise RuntimeError("Missing required function public.set_updated_at(); run DB vNext 0001 first.")

    op.execute("CREATE SCHEMA IF NOT EXISTS leave")

    # ------------------------------------------------------------------
    # leave.leave_types
    # ------------------------------------------------------------------
    op.create_table(
        "leave_types",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("is_paid", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("unit", sa.Text(), nullable=False, server_default=sa.text("'DAY'")),
        sa.Column("requires_attachment", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("allow_negative_balance", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("max_consecutive_days", sa.Integer(), nullable=True),
        sa.Column("min_notice_days", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("unit in ('DAY','HALF_DAY')", name="ck_leave_types_unit"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_leave_types_tenant_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "code", name="uq_leave_types_tenant_code"),
        schema="leave",
    )
    op.create_index(
        "ix_leave_types_tenant_is_active",
        "leave_types",
        ["tenant_id", "is_active"],
        unique=False,
        schema="leave",
    )
    _create_updated_at_trigger("leave", "leave_types")

    # ------------------------------------------------------------------
    # leave.leave_policies
    # ------------------------------------------------------------------
    op.create_table(
        "leave_policies",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("year_start_month", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("year_start_month >= 1 AND year_start_month <= 12", name="ck_leave_policies_year_start_month"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_leave_policies_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_leave_policies_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_leave_policies_branch_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "code", name="uq_leave_policies_tenant_code"),
        schema="leave",
    )
    _create_updated_at_trigger("leave", "leave_policies")

    # ------------------------------------------------------------------
    # leave.leave_policy_rules
    # ------------------------------------------------------------------
    op.create_table(
        "leave_policy_rules",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("leave_type_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "annual_entitlement_days",
            sa.Numeric(6, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("allow_half_day", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires_attachment", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_leave_policy_rules_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["leave.leave_policies.id"],
            name="fk_leave_policy_rules_policy_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["leave_type_id"],
            ["leave.leave_types.id"],
            name="fk_leave_policy_rules_leave_type_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("tenant_id", "policy_id", "leave_type_id", name="uq_leave_policy_rules_unique"),
        schema="leave",
    )

    # ------------------------------------------------------------------
    # leave.employee_leave_policy
    # ------------------------------------------------------------------
    op.create_table(
        "employee_leave_policy",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_employee_leave_policy_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_employee_leave_policy_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["leave.leave_policies.id"],
            name="fk_employee_leave_policy_policy_id",
            ondelete="CASCADE",
        ),
        schema="leave",
    )
    op.create_index(
        "uq_employee_leave_policy_active",
        "employee_leave_policy",
        ["tenant_id", "employee_id"],
        unique=True,
        schema="leave",
        postgresql_where=sa.text("effective_to IS NULL"),
    )

    # ------------------------------------------------------------------
    # leave.leave_ledger
    # ------------------------------------------------------------------
    op.create_table(
        "leave_ledger",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("leave_type_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_year", sa.Integer(), nullable=False),
        sa.Column("delta_days", sa.Numeric(6, 2), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "source_type in ('ALLOCATION','LEAVE_REQUEST','ADJUSTMENT','CARRYOVER')",
            name="ck_leave_ledger_source_type",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_leave_ledger_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_leave_ledger_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["leave_type_id"],
            ["leave.leave_types.id"],
            name="fk_leave_ledger_leave_type_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["iam.users.id"],
            name="fk_leave_ledger_created_by_user_id",
            ondelete="SET NULL",
        ),
        schema="leave",
    )
    op.create_index(
        "ix_leave_ledger_employee_type_year",
        "leave_ledger",
        ["tenant_id", "employee_id", "leave_type_id", "period_year"],
        unique=False,
        schema="leave",
    )
    op.create_index(
        "ix_leave_ledger_source",
        "leave_ledger",
        ["tenant_id", "source_type", "source_id"],
        unique=False,
        schema="leave",
    )
    op.create_index(
        "uq_leave_ledger_leave_request_idem",
        "leave_ledger",
        ["tenant_id", "source_type", "source_id", "leave_type_id"],
        unique=True,
        schema="leave",
        postgresql_where=sa.text("source_type = 'LEAVE_REQUEST' AND source_id IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # leave.leave_requests
    # ------------------------------------------------------------------
    op.create_table(
        "leave_requests",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("leave_type_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=False),
        sa.Column("half_day_part", sa.Text(), nullable=True),
        sa.Column("requested_days", sa.Numeric(6, 2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("workflow_request_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("unit in ('DAY','HALF_DAY')", name="ck_leave_requests_unit"),
        sa.CheckConstraint("half_day_part in ('AM','PM') OR half_day_part IS NULL", name="ck_leave_requests_half_day_part"),
        sa.CheckConstraint(
            "status in ('DRAFT','PENDING','APPROVED','REJECTED','CANCELED')",
            name="ck_leave_requests_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_leave_requests_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_leave_requests_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["leave_type_id"],
            ["leave.leave_types.id"],
            name="fk_leave_requests_leave_type_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["leave.leave_policies.id"],
            name="fk_leave_requests_policy_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_request_id"],
            ["workflow.requests.id"],
            name="fk_leave_requests_workflow_request_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_leave_requests_company_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_leave_requests_branch_id",
            ondelete="SET NULL",
        ),
        schema="leave",
    )
    op.create_index(
        "ix_leave_requests_employee_created_at",
        "leave_requests",
        ["tenant_id", "employee_id", "created_at"],
        unique=False,
        schema="leave",
    )
    op.create_index(
        "ix_leave_requests_branch_dates",
        "leave_requests",
        ["tenant_id", "branch_id", "start_date", "end_date"],
        unique=False,
        schema="leave",
    )
    op.create_index(
        "uq_leave_requests_idempotency",
        "leave_requests",
        ["tenant_id", "employee_id", "idempotency_key"],
        unique=True,
        schema="leave",
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    _create_updated_at_trigger("leave", "leave_requests")

    # ------------------------------------------------------------------
    # leave.leave_request_days
    # ------------------------------------------------------------------
    op.create_table(
        "leave_request_days",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("leave_request_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("countable", sa.Boolean(), nullable=False),
        sa.Column("day_fraction", sa.Numeric(3, 2), nullable=False),
        sa.Column("is_weekend", sa.Boolean(), nullable=False),
        sa.Column("is_holiday", sa.Boolean(), nullable=False),
        sa.Column("holiday_name", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_leave_request_days_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["leave_request_id"],
            ["leave.leave_requests.id"],
            name="fk_leave_request_days_leave_request_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_leave_request_days_employee_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("tenant_id", "leave_request_id", "day", name="uq_leave_request_days_unique"),
        schema="leave",
    )
    op.create_index(
        "ix_leave_request_days_employee_day",
        "leave_request_days",
        ["tenant_id", "employee_id", "day"],
        unique=False,
        schema="leave",
    )
    op.create_index(
        "ix_leave_request_days_day",
        "leave_request_days",
        ["tenant_id", "day"],
        unique=False,
        schema="leave",
    )

    # ------------------------------------------------------------------
    # leave.holidays (tenant-wide and branch-scoped)
    # ------------------------------------------------------------------
    op.create_table(
        "holidays",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("branch_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_leave_holidays_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["tenancy.companies.id"],
            name="fk_leave_holidays_company_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_leave_holidays_branch_id",
            ondelete="CASCADE",
        ),
        schema="leave",
    )
    # Global holidays: unique (tenant_id, day) when no company/branch scope.
    op.create_index(
        "uq_leave_holidays_global",
        "holidays",
        ["tenant_id", "day"],
        unique=True,
        schema="leave",
        postgresql_where=sa.text("branch_id IS NULL AND company_id IS NULL"),
    )
    # Branch holidays: unique (tenant_id, branch_id, day) when branch scoped.
    op.create_index(
        "uq_leave_holidays_branch",
        "holidays",
        ["tenant_id", "branch_id", "day"],
        unique=True,
        schema="leave",
        postgresql_where=sa.text("branch_id IS NOT NULL"),
    )
    op.create_index(
        "ix_leave_holidays_tenant_branch_day",
        "holidays",
        ["tenant_id", "branch_id", "day"],
        unique=False,
        schema="leave",
    )

    # ------------------------------------------------------------------
    # leave.weekly_off (required config: 7 rows per branch)
    # ------------------------------------------------------------------
    op.create_table(
        "weekly_off",
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("is_off", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.CheckConstraint("weekday >= 0 AND weekday <= 6", name="ck_leave_weekly_off_weekday"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_leave_weekly_off_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_leave_weekly_off_branch_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("tenant_id", "branch_id", "weekday", name="pk_leave_weekly_off"),
        schema="leave",
    )


def downgrade() -> None:
    op.drop_table("weekly_off", schema="leave")
    op.drop_index("ix_leave_holidays_tenant_branch_day", table_name="holidays", schema="leave")
    op.drop_index("uq_leave_holidays_branch", table_name="holidays", schema="leave")
    op.drop_index("uq_leave_holidays_global", table_name="holidays", schema="leave")
    op.drop_table("holidays", schema="leave")

    op.drop_index("ix_leave_request_days_day", table_name="leave_request_days", schema="leave")
    op.drop_index("ix_leave_request_days_employee_day", table_name="leave_request_days", schema="leave")
    op.drop_table("leave_request_days", schema="leave")

    op.drop_index("uq_leave_requests_idempotency", table_name="leave_requests", schema="leave")
    op.drop_index("ix_leave_requests_branch_dates", table_name="leave_requests", schema="leave")
    op.drop_index("ix_leave_requests_employee_created_at", table_name="leave_requests", schema="leave")
    op.drop_table("leave_requests", schema="leave")

    op.drop_index("uq_leave_ledger_leave_request_idem", table_name="leave_ledger", schema="leave")
    op.drop_index("ix_leave_ledger_source", table_name="leave_ledger", schema="leave")
    op.drop_index("ix_leave_ledger_employee_type_year", table_name="leave_ledger", schema="leave")
    op.drop_table("leave_ledger", schema="leave")

    op.drop_index("uq_employee_leave_policy_active", table_name="employee_leave_policy", schema="leave")
    op.drop_table("employee_leave_policy", schema="leave")

    op.drop_table("leave_policy_rules", schema="leave")
    op.drop_table("leave_policies", schema="leave")

    op.drop_index("ix_leave_types_tenant_is_active", table_name="leave_types", schema="leave")
    op.drop_table("leave_types", schema="leave")

    op.execute("DROP SCHEMA IF EXISTS leave")

