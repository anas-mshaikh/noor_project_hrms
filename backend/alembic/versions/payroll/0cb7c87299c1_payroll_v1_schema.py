"""Payroll foundation v1: schema objects.

Revision ID: 0cb7c87299c1
Revises: ee9edafad310
Create Date: 2026-02-21

Milestone 9 introduces a payroll foundation under schema `payroll`:
- Payroll setup: calendars/periods, components, salary structures, compensation.
- Payrun engine outputs: payruns, per-employee payrun_items, payrun_item_lines.
- Payslip tracking: payslips linked to DMS documents.

Design notes:
- Money uses NUMERIC (not float) to preserve precision.
- Mutable tables use the repo-standard `public.set_updated_at()` trigger.
- Enumerations are enforced via CHECK constraints (forward compatible with
  future country packs by expanding allowed values through migrations).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as psql


# revision identifiers, used by Alembic.
revision = "0cb7c87299c1"
down_revision = "ee9edafad310"
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
    # The baseline migration creates public.set_updated_at(). If it's missing,
    # fail loudly to avoid creating partially-upgraded schemas.
    conn = op.get_bind()
    fn = conn.execute(sa.text("SELECT to_regprocedure('public.set_updated_at()')")).scalar()
    if fn is None:
        raise RuntimeError("Missing required function public.set_updated_at(); run baseline first.")

    op.execute("CREATE SCHEMA IF NOT EXISTS payroll")

    # ------------------------------------------------------------------
    # payroll.calendars
    # ------------------------------------------------------------------
    op.create_table(
        "calendars",
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
        sa.Column("frequency", sa.Text(), nullable=False, server_default=sa.text("'MONTHLY'")),
        sa.Column("currency_code", sa.Text(), nullable=False),
        sa.Column("timezone", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("frequency in ('MONTHLY')", name="ck_payroll_calendars_frequency"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_payroll_calendars_code"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_payroll_calendars_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["iam.users.id"],
            name="fk_payroll_calendars_created_by_user_id",
            ondelete="SET NULL",
        ),
        schema="payroll",
    )
    op.create_index(
        "ix_payroll_calendars_tenant_active",
        "calendars",
        ["tenant_id", "is_active"],
        unique=False,
        schema="payroll",
    )
    _create_updated_at_trigger("payroll", "calendars")

    # ------------------------------------------------------------------
    # payroll.periods
    # ------------------------------------------------------------------
    op.create_table(
        "periods",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("calendar_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_key", sa.Text(), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'OPEN'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status in ('OPEN','CLOSED')", name="ck_payroll_periods_status"),
        sa.CheckConstraint("start_date <= end_date", name="ck_payroll_periods_date_range"),
        sa.UniqueConstraint("tenant_id", "calendar_id", "period_key", name="uq_payroll_periods_key"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_payroll_periods_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["calendar_id"],
            ["payroll.calendars.id"],
            name="fk_payroll_periods_calendar_id",
            ondelete="CASCADE",
        ),
        schema="payroll",
    )
    op.create_index(
        "ix_payroll_periods_tenant_dates",
        "periods",
        ["tenant_id", "start_date", "end_date"],
        unique=False,
        schema="payroll",
    )
    _create_updated_at_trigger("payroll", "periods")

    # ------------------------------------------------------------------
    # payroll.components
    # ------------------------------------------------------------------
    op.create_table(
        "components",
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
        sa.Column("component_type", sa.Text(), nullable=False),
        sa.Column("calc_mode", sa.Text(), nullable=False, server_default=sa.text("'FIXED'")),
        sa.Column("default_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("default_percent", sa.Numeric(6, 3), nullable=True),
        sa.Column("is_taxable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "component_type in ('EARNING','DEDUCTION')",
            name="ck_payroll_components_type",
        ),
        sa.CheckConstraint(
            "calc_mode in ('FIXED','PERCENT_OF_GROSS','MANUAL')",
            name="ck_payroll_components_calc_mode",
        ),
        sa.UniqueConstraint("tenant_id", "code", name="uq_payroll_components_code"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_payroll_components_tenant_id",
            ondelete="CASCADE",
        ),
        schema="payroll",
    )
    op.create_index(
        "ix_payroll_components_tenant_type_active",
        "components",
        ["tenant_id", "component_type", "is_active"],
        unique=False,
        schema="payroll",
    )
    _create_updated_at_trigger("payroll", "components")

    # ------------------------------------------------------------------
    # payroll.salary_structures
    # ------------------------------------------------------------------
    op.create_table(
        "salary_structures",
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
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "code", name="uq_payroll_salary_structures_code"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_payroll_salary_structures_tenant_id",
            ondelete="CASCADE",
        ),
        schema="payroll",
    )
    op.create_index(
        "ix_payroll_salary_structures_tenant_active",
        "salary_structures",
        ["tenant_id", "is_active"],
        unique=False,
        schema="payroll",
    )
    _create_updated_at_trigger("payroll", "salary_structures")

    # ------------------------------------------------------------------
    # payroll.salary_structure_lines
    # ------------------------------------------------------------------
    op.create_table(
        "salary_structure_lines",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("salary_structure_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("component_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("calc_mode_override", sa.Text(), nullable=True),
        sa.Column("amount_override", sa.Numeric(14, 2), nullable=True),
        sa.Column("percent_override", sa.Numeric(6, 3), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "calc_mode_override is null or calc_mode_override in ('FIXED','PERCENT_OF_GROSS','MANUAL')",
            name="ck_payroll_salary_structure_lines_calc_mode_override",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "salary_structure_id",
            "component_id",
            name="uq_payroll_salary_structure_lines_component",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_payroll_salary_structure_lines_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["salary_structure_id"],
            ["payroll.salary_structures.id"],
            name="fk_payroll_salary_structure_lines_structure_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["payroll.components.id"],
            name="fk_payroll_salary_structure_lines_component_id",
            ondelete="RESTRICT",
        ),
        schema="payroll",
    )
    op.create_index(
        "ix_payroll_salary_structure_lines_structure_sort",
        "salary_structure_lines",
        ["tenant_id", "salary_structure_id", "sort_order"],
        unique=False,
        schema="payroll",
    )

    # ------------------------------------------------------------------
    # payroll.employee_compensations (effective-dated)
    # ------------------------------------------------------------------
    op.create_table(
        "employee_compensations",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency_code", sa.Text(), nullable=False),
        sa.Column("salary_structure_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("base_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("overrides_json", psql.JSONB(), nullable=True),
        sa.Column("created_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "effective_to is null or effective_from <= effective_to",
            name="ck_payroll_employee_compensations_date_range",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_payroll_employee_compensations_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_payroll_employee_compensations_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["salary_structure_id"],
            ["payroll.salary_structures.id"],
            name="fk_payroll_employee_compensations_structure_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["iam.users.id"],
            name="fk_payroll_employee_compensations_created_by_user_id",
            ondelete="SET NULL",
        ),
        schema="payroll",
    )
    # One active row per employee (effective_to IS NULL).
    op.create_index(
        "uq_payroll_employee_compensations_employee_active",
        "employee_compensations",
        ["tenant_id", "employee_id"],
        unique=True,
        schema="payroll",
        postgresql_where=sa.text("effective_to IS NULL"),
    )
    op.create_index(
        "ix_payroll_employee_compensations_employee_effective_from",
        "employee_compensations",
        ["tenant_id", "employee_id", "effective_from"],
        unique=False,
        schema="payroll",
    )
    _create_updated_at_trigger("payroll", "employee_compensations")

    # ------------------------------------------------------------------
    # payroll.payruns
    # ------------------------------------------------------------------
    op.create_table(
        "payruns",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("calendar_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("period_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default=sa.text("1")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'DRAFT'")),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("generated_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("workflow_request_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("totals_json", psql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status in ('DRAFT','PENDING_APPROVAL','APPROVED','PUBLISHED','CANCELED')",
            name="ck_payroll_payruns_status",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "period_id",
            "branch_id",
            "version",
            name="uq_payroll_payruns_period_branch_version",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_payroll_payruns_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["calendar_id"],
            ["payroll.calendars.id"],
            name="fk_payroll_payruns_calendar_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["period_id"],
            ["payroll.periods.id"],
            name="fk_payroll_payruns_period_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_payroll_payruns_branch_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["generated_by_user_id"],
            ["iam.users.id"],
            name="fk_payroll_payruns_generated_by_user_id",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_request_id"],
            ["workflow.requests.id"],
            name="fk_payroll_payruns_workflow_request_id",
            ondelete="SET NULL",
        ),
        schema="payroll",
    )
    op.create_index(
        "ix_payroll_payruns_tenant_period_status",
        "payruns",
        ["tenant_id", "period_id", "status"],
        unique=False,
        schema="payroll",
    )
    op.create_index(
        "uq_payroll_payruns_idempotency",
        "payruns",
        ["tenant_id", "period_id", "branch_id", "idempotency_key"],
        unique=True,
        schema="payroll",
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    _create_updated_at_trigger("payroll", "payruns")

    # ------------------------------------------------------------------
    # payroll.payrun_items (per employee)
    # ------------------------------------------------------------------
    op.create_table(
        "payrun_items",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("payrun_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("payable_days", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("payable_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("working_days_in_period", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("gross_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("deductions_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("net_amount", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'INCLUDED'")),
        sa.Column("computed_json", psql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("anomalies_json", psql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status in ('INCLUDED','EXCLUDED')", name="ck_payroll_payrun_items_status"),
        sa.UniqueConstraint("tenant_id", "payrun_id", "employee_id", name="uq_payroll_payrun_items_employee"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_payroll_payrun_items_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payrun_id"],
            ["payroll.payruns.id"],
            name="fk_payroll_payrun_items_payrun_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_payroll_payrun_items_employee_id",
            ondelete="CASCADE",
        ),
        schema="payroll",
    )
    op.create_index(
        "ix_payroll_payrun_items_payrun",
        "payrun_items",
        ["tenant_id", "payrun_id"],
        unique=False,
        schema="payroll",
    )
    op.create_index(
        "ix_payroll_payrun_items_employee",
        "payrun_items",
        ["tenant_id", "employee_id"],
        unique=False,
        schema="payroll",
    )

    # ------------------------------------------------------------------
    # payroll.payrun_item_lines (component line items)
    # ------------------------------------------------------------------
    op.create_table(
        "payrun_item_lines",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("payrun_item_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("component_id", psql.UUID(as_uuid=True), nullable=False),
        # Denormalized for stability/traceability (components may change later).
        sa.Column("component_code", sa.Text(), nullable=False),
        sa.Column("component_type", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("meta_json", psql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_payroll_payrun_item_lines_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payrun_item_id"],
            ["payroll.payrun_items.id"],
            name="fk_payroll_payrun_item_lines_item_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["component_id"],
            ["payroll.components.id"],
            name="fk_payroll_payrun_item_lines_component_id",
            ondelete="RESTRICT",
        ),
        schema="payroll",
    )
    op.create_index(
        "ix_payroll_payrun_item_lines_item",
        "payrun_item_lines",
        ["tenant_id", "payrun_item_id"],
        unique=False,
        schema="payroll",
    )

    # ------------------------------------------------------------------
    # payroll.payslips
    # ------------------------------------------------------------------
    op.create_table(
        "payslips",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("payrun_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'READY'")),
        sa.Column("dms_document_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status in ('READY','PUBLISHED')", name="ck_payroll_payslips_status"),
        sa.UniqueConstraint("tenant_id", "payrun_id", "employee_id", name="uq_payroll_payslips_employee"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_payroll_payslips_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["payrun_id"],
            ["payroll.payruns.id"],
            name="fk_payroll_payslips_payrun_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_payroll_payslips_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["dms_document_id"],
            ["dms.documents.id"],
            name="fk_payroll_payslips_dms_document_id",
            ondelete="SET NULL",
        ),
        schema="payroll",
    )
    op.create_index(
        "ix_payroll_payslips_employee_created_at",
        "payslips",
        ["tenant_id", "employee_id", "created_at"],
        unique=False,
        schema="payroll",
        postgresql_using="btree",
    )
    _create_updated_at_trigger("payroll", "payslips")


def downgrade() -> None:
    op.drop_index("ix_payroll_payslips_employee_created_at", table_name="payslips", schema="payroll")
    op.drop_table("payslips", schema="payroll")

    op.drop_index("ix_payroll_payrun_item_lines_item", table_name="payrun_item_lines", schema="payroll")
    op.drop_table("payrun_item_lines", schema="payroll")

    op.drop_index("ix_payroll_payrun_items_employee", table_name="payrun_items", schema="payroll")
    op.drop_index("ix_payroll_payrun_items_payrun", table_name="payrun_items", schema="payroll")
    op.drop_table("payrun_items", schema="payroll")

    op.drop_index("uq_payroll_payruns_idempotency", table_name="payruns", schema="payroll")
    op.drop_index("ix_payroll_payruns_tenant_period_status", table_name="payruns", schema="payroll")
    op.drop_table("payruns", schema="payroll")

    op.drop_index(
        "ix_payroll_employee_compensations_employee_effective_from",
        table_name="employee_compensations",
        schema="payroll",
    )
    op.drop_index(
        "uq_payroll_employee_compensations_employee_active",
        table_name="employee_compensations",
        schema="payroll",
    )
    op.drop_table("employee_compensations", schema="payroll")

    op.drop_index(
        "ix_payroll_salary_structure_lines_structure_sort",
        table_name="salary_structure_lines",
        schema="payroll",
    )
    op.drop_table("salary_structure_lines", schema="payroll")

    op.drop_index("ix_payroll_salary_structures_tenant_active", table_name="salary_structures", schema="payroll")
    op.drop_table("salary_structures", schema="payroll")

    op.drop_index(
        "ix_payroll_components_tenant_type_active",
        table_name="components",
        schema="payroll",
    )
    op.drop_table("components", schema="payroll")

    op.drop_index(
        "ix_payroll_periods_tenant_dates",
        table_name="periods",
        schema="payroll",
    )
    op.drop_table("periods", schema="payroll")

    op.drop_index("ix_payroll_calendars_tenant_active", table_name="calendars", schema="payroll")
    op.drop_table("calendars", schema="payroll")

    op.execute("DROP SCHEMA IF EXISTS payroll")

