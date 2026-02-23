"""Roster v1 + payable summaries: schema objects.

Revision ID: e97254580575
Revises: 7d5dc0b6d1ff
Create Date: 2026-02-20

Milestone 8 introduces a first-class scheduling layer:
- `roster.shift_templates`: reusable shift definitions per branch.
- `roster.branch_defaults`: optional default shift per branch.
- `roster.shift_assignments`: effective-dated employee shift assignments.
- `roster.roster_overrides`: per-employee per-day overrides (shift change / weekoff / workday).

It also introduces a payroll-ready, materialized output:
- `attendance.payable_day_summaries`: one row per employee/day with expected/worked/payable
  minutes and traceability fields.

Design notes:
- We attach the repo-standard updated_at trigger (public.set_updated_at()) to the mutable
  roster tables. Payable summaries are materialized and updated by services, so we keep
  a simple `computed_at` timestamp instead.
- Shift templates support overnight shifts in application code (end_time <= start_time
  means "ends next day"). We intentionally do not enforce that at the DB level.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as psql


# revision identifiers, used by Alembic.
revision = "e97254580575"
down_revision = "7d5dc0b6d1ff"
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
    # we fail loudly to avoid creating partially-upgraded schemas.
    conn = op.get_bind()
    fn = conn.execute(sa.text("SELECT to_regprocedure('public.set_updated_at()')")).scalar()
    if fn is None:
        raise RuntimeError("Missing required function public.set_updated_at(); run baseline first.")

    op.execute("CREATE SCHEMA IF NOT EXISTS roster")
    op.execute("CREATE SCHEMA IF NOT EXISTS attendance")

    # ------------------------------------------------------------------
    # roster.shift_templates
    # ------------------------------------------------------------------
    op.create_table(
        "shift_templates",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("break_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Placeholders for future policy engine work (grace/partial day).
        sa.Column("grace_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("min_full_day_minutes", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("tenant_id", "branch_id", "code", name="uq_shift_templates_branch_code"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_shift_templates_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_shift_templates_branch_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["iam.users.id"],
            name="fk_shift_templates_created_by_user_id",
            ondelete="SET NULL",
        ),
        schema="roster",
    )
    op.create_index(
        "ix_shift_templates_branch_active",
        "shift_templates",
        ["tenant_id", "branch_id", "is_active"],
        unique=False,
        schema="roster",
    )
    _create_updated_at_trigger("roster", "shift_templates")

    # ------------------------------------------------------------------
    # roster.branch_defaults
    # ------------------------------------------------------------------
    op.create_table(
        "branch_defaults",
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("default_shift_template_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("tenant_id", "branch_id", name="pk_branch_defaults"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_branch_defaults_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_branch_defaults_branch_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["default_shift_template_id"],
            ["roster.shift_templates.id"],
            name="fk_branch_defaults_shift_template_id",
            ondelete="RESTRICT",
        ),
        schema="roster",
    )
    _create_updated_at_trigger("roster", "branch_defaults")

    # ------------------------------------------------------------------
    # roster.shift_assignments (effective-dated)
    # ------------------------------------------------------------------
    op.create_table(
        "shift_assignments",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", psql.UUID(as_uuid=True), nullable=False),
        # Snapshot from current employment at assignment time.
        sa.Column("branch_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("shift_template_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("created_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_shift_assignments_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_shift_assignments_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_shift_assignments_branch_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shift_template_id"],
            ["roster.shift_templates.id"],
            name="fk_shift_assignments_shift_template_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["iam.users.id"],
            name="fk_shift_assignments_created_by_user_id",
            ondelete="SET NULL",
        ),
        schema="roster",
    )
    # One active assignment per employee (effective_to IS NULL).
    op.create_index(
        "uq_shift_assignments_employee_active",
        "shift_assignments",
        ["tenant_id", "employee_id"],
        unique=True,
        schema="roster",
        postgresql_where=sa.text("effective_to IS NULL"),
    )
    op.create_index(
        "ix_shift_assignments_employee_effective_from",
        "shift_assignments",
        ["tenant_id", "employee_id", "effective_from"],
        unique=False,
        schema="roster",
    )
    op.create_index(
        "ix_shift_assignments_branch_effective_from",
        "shift_assignments",
        ["tenant_id", "branch_id", "effective_from"],
        unique=False,
        schema="roster",
    )
    _create_updated_at_trigger("roster", "shift_assignments")

    # ------------------------------------------------------------------
    # roster.roster_overrides (per employee per day)
    # ------------------------------------------------------------------
    op.create_table(
        "roster_overrides",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", psql.UUID(as_uuid=True), nullable=False),
        # Snapshot from current employment at create time.
        sa.Column("branch_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("override_type", sa.Text(), nullable=False),
        sa.Column("shift_template_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "override_type in ('SHIFT_CHANGE','WEEKOFF','WORKDAY')",
            name="ck_roster_overrides_override_type",
        ),
        sa.UniqueConstraint("tenant_id", "employee_id", "day", name="uq_roster_overrides_employee_day"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_roster_overrides_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_roster_overrides_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_roster_overrides_branch_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shift_template_id"],
            ["roster.shift_templates.id"],
            name="fk_roster_overrides_shift_template_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["iam.users.id"],
            name="fk_roster_overrides_created_by_user_id",
            ondelete="SET NULL",
        ),
        schema="roster",
    )
    op.create_index(
        "ix_roster_overrides_branch_day",
        "roster_overrides",
        ["tenant_id", "branch_id", "day"],
        unique=False,
        schema="roster",
    )
    _create_updated_at_trigger("roster", "roster_overrides")

    # ------------------------------------------------------------------
    # attendance.payable_day_summaries (materialized payroll-ready output)
    # ------------------------------------------------------------------
    op.create_table(
        "payable_day_summaries",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("shift_template_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("day_type", sa.Text(), nullable=False),
        sa.Column("presence_status", sa.Text(), nullable=False),
        sa.Column("expected_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("worked_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("payable_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        # Placeholders for future policy engine (late/overtime).
        sa.Column("late_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("overtime_minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("anomalies_json", psql.JSONB(), nullable=True),
        sa.Column("source_breakdown", psql.JSONB(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "day_type in ('WORKDAY','WEEKOFF','HOLIDAY','ON_LEAVE','UNSCHEDULED')",
            name="ck_payable_day_summaries_day_type",
        ),
        sa.CheckConstraint(
            "presence_status in ('PRESENT','ABSENT','N_A')",
            name="ck_payable_day_summaries_presence_status",
        ),
        sa.UniqueConstraint("tenant_id", "employee_id", "day", name="uq_payable_day_summaries_employee_day"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_payable_day_summaries_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_payable_day_summaries_branch_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_payable_day_summaries_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["shift_template_id"],
            ["roster.shift_templates.id"],
            name="fk_payable_day_summaries_shift_template_id",
            ondelete="SET NULL",
        ),
        schema="attendance",
    )
    op.create_index(
        "ix_payable_day_summaries_branch_day",
        "payable_day_summaries",
        ["tenant_id", "branch_id", "day"],
        unique=False,
        schema="attendance",
    )
    op.create_index(
        "ix_payable_day_summaries_employee_day",
        "payable_day_summaries",
        ["tenant_id", "employee_id", "day"],
        unique=False,
        schema="attendance",
    )


def downgrade() -> None:
    op.drop_index("ix_payable_day_summaries_employee_day", table_name="payable_day_summaries", schema="attendance")
    op.drop_index("ix_payable_day_summaries_branch_day", table_name="payable_day_summaries", schema="attendance")
    op.drop_table("payable_day_summaries", schema="attendance")

    op.drop_index("ix_roster_overrides_branch_day", table_name="roster_overrides", schema="roster")
    op.drop_table("roster_overrides", schema="roster")

    op.drop_index("ix_shift_assignments_branch_effective_from", table_name="shift_assignments", schema="roster")
    op.drop_index("ix_shift_assignments_employee_effective_from", table_name="shift_assignments", schema="roster")
    op.drop_index("uq_shift_assignments_employee_active", table_name="shift_assignments", schema="roster")
    op.drop_table("shift_assignments", schema="roster")

    op.drop_table("branch_defaults", schema="roster")

    op.drop_index("ix_shift_templates_branch_active", table_name="shift_templates", schema="roster")
    op.drop_table("shift_templates", schema="roster")

    op.execute("DROP SCHEMA IF EXISTS roster")

