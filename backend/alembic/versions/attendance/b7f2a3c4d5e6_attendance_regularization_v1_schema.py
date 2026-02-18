"""Attendance regularization v1: day overrides + correction requests.

Revision ID: b7f2a3c4d5e6
Revises: 000000000000
Create Date: 2026-02-17

Milestone 4 introduces an attendance correction flow powered by the workflow
engine. Approved corrections write deterministic overrides into
attendance.day_overrides.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as psql


# revision identifiers, used by Alembic.
revision = "b7f2a3c4d5e6"
down_revision = "000000000000"
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
        raise RuntimeError("Missing required function public.set_updated_at(); run baseline first.")

    op.execute("CREATE SCHEMA IF NOT EXISTS attendance")

    # ------------------------------------------------------------------
    # attendance.day_overrides: extend beyond leave-only overrides
    # ------------------------------------------------------------------
    op.add_column(
        "day_overrides",
        sa.Column("override_kind", sa.Text(), nullable=False, server_default=sa.text("'LEAVE'")),
        schema="attendance",
    )
    op.add_column("day_overrides", sa.Column("notes", sa.Text(), nullable=True), schema="attendance")
    op.add_column("day_overrides", sa.Column("payload", psql.JSONB(), nullable=True), schema="attendance")

    # Defensive backfill for dev DBs created before this migration.
    op.execute(sa.text("UPDATE attendance.day_overrides SET override_kind = 'LEAVE' WHERE override_kind IS NULL"))

    # Replace CHECK constraints (v1 now supports leave + correction overrides).
    op.drop_constraint("ck_day_overrides_status", "day_overrides", schema="attendance", type_="check")
    op.drop_constraint("ck_day_overrides_source_type", "day_overrides", schema="attendance", type_="check")
    op.create_check_constraint(
        "ck_day_overrides_override_kind",
        "day_overrides",
        "override_kind in ('LEAVE','CORRECTION')",
        schema="attendance",
    )
    op.create_check_constraint(
        "ck_day_overrides_status",
        "day_overrides",
        "status in ('ON_LEAVE','PRESENT_OVERRIDE','ABSENT_OVERRIDE','WFH','ON_DUTY')",
        schema="attendance",
    )
    op.create_check_constraint(
        "ck_day_overrides_source_type",
        "day_overrides",
        "source_type in ('LEAVE_REQUEST','ATTENDANCE_CORRECTION')",
        schema="attendance",
    )

    # Helpful for branch/day summary queries.
    op.create_index(
        "ix_day_overrides_branch_day",
        "day_overrides",
        ["tenant_id", "branch_id", "day"],
        unique=False,
        schema="attendance",
    )

    # ------------------------------------------------------------------
    # attendance.attendance_corrections
    # ------------------------------------------------------------------
    op.create_table(
        "attendance_corrections",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("correction_type", sa.Text(), nullable=False),
        sa.Column("requested_override_status", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("evidence_file_ids", psql.ARRAY(psql.UUID(as_uuid=True)), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("workflow_request_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "correction_type in ('MISSED_PUNCH','MARK_PRESENT','MARK_ABSENT','WFH','ON_DUTY')",
            name="ck_attendance_corrections_correction_type",
        ),
        sa.CheckConstraint(
            "requested_override_status in ('PRESENT_OVERRIDE','ABSENT_OVERRIDE','WFH','ON_DUTY')",
            name="ck_attendance_corrections_requested_override_status",
        ),
        sa.CheckConstraint(
            "status in ('PENDING','APPROVED','REJECTED','CANCELED')",
            name="ck_attendance_corrections_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_attendance_corrections_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_attendance_corrections_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_attendance_corrections_branch_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_request_id"],
            ["workflow.requests.id"],
            name="fk_attendance_corrections_workflow_request_id",
            ondelete="RESTRICT",
        ),
        schema="attendance",
    )

    op.create_index(
        "uq_attendance_corrections_idempotency",
        "attendance_corrections",
        ["tenant_id", "employee_id", "idempotency_key"],
        unique=True,
        schema="attendance",
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )
    op.create_index(
        "uq_attendance_corrections_pending_day",
        "attendance_corrections",
        ["tenant_id", "employee_id", "day"],
        unique=True,
        schema="attendance",
        postgresql_where=sa.text("status = 'PENDING'"),
    )
    op.create_index(
        "ix_attendance_corrections_employee_day",
        "attendance_corrections",
        ["tenant_id", "employee_id", "day"],
        unique=False,
        schema="attendance",
    )
    op.create_index(
        "ix_attendance_corrections_branch_day",
        "attendance_corrections",
        ["tenant_id", "branch_id", "day"],
        unique=False,
        schema="attendance",
    )

    _create_updated_at_trigger("attendance", "attendance_corrections")


def downgrade() -> None:
    op.drop_index(
        "ix_attendance_corrections_branch_day",
        table_name="attendance_corrections",
        schema="attendance",
    )
    op.drop_index(
        "ix_attendance_corrections_employee_day",
        table_name="attendance_corrections",
        schema="attendance",
    )
    op.drop_index(
        "uq_attendance_corrections_pending_day",
        table_name="attendance_corrections",
        schema="attendance",
    )
    op.drop_index(
        "uq_attendance_corrections_idempotency",
        table_name="attendance_corrections",
        schema="attendance",
    )
    op.drop_table("attendance_corrections", schema="attendance")

    op.drop_index("ix_day_overrides_branch_day", table_name="day_overrides", schema="attendance")

    op.drop_constraint("ck_day_overrides_override_kind", "day_overrides", schema="attendance", type_="check")
    op.drop_constraint("ck_day_overrides_status", "day_overrides", schema="attendance", type_="check")
    op.drop_constraint("ck_day_overrides_source_type", "day_overrides", schema="attendance", type_="check")

    # Restore leave-only checks.
    op.create_check_constraint(
        "ck_day_overrides_source_type",
        "day_overrides",
        "source_type = 'LEAVE_REQUEST'",
        schema="attendance",
    )
    op.create_check_constraint(
        "ck_day_overrides_status",
        "day_overrides",
        "status = 'ON_LEAVE'",
        schema="attendance",
    )

    op.drop_column("day_overrides", "payload", schema="attendance")
    op.drop_column("day_overrides", "notes", schema="attendance")
    op.drop_column("day_overrides", "override_kind", schema="attendance")

