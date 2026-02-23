"""Attendance punching v1: punches, work sessions, and daily extensions.

Revision ID: b3ef9f746c38
Revises: a5b6c7d8e9f0
Create Date: 2026-02-20

Milestone 7 introduces a Zoho-style punch-in/out toggle model:
- Immutable punch events (attendance.punches)
- Paired work sessions derived from punches (attendance.work_sessions)
- Branch-level punch settings (attendance.punch_settings)

We also extend attendance.attendance_daily to carry:
- source_breakdown (jsonb): minutes grouped by punch/session source
- has_open_session (bool): quick "am I punched in?" state

Design notes:
- Business date is derived in application code using the branch timezone.
- `attendance.attendance_daily` remains a derived/rollup table that can be
  populated by both legacy vision rollups and the punching pipeline.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as psql


# revision identifiers, used by Alembic.
revision = "b3ef9f746c38"
down_revision = "a5b6c7d8e9f0"
branch_labels = None
depends_on = None


SOURCES = (
    "MANUAL_WEB",
    "MANUAL_MOBILE",
    "SYSTEM",
    "BIOMETRIC",
    "CCTV",
    "IMPORT",
)


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
    # Ensure the standard trigger function exists (baseline creates it).
    conn = op.get_bind()
    fn = conn.execute(sa.text("SELECT to_regprocedure('public.set_updated_at()')")).scalar()
    if fn is None:
        raise RuntimeError("Missing required function public.set_updated_at(); run baseline first.")

    op.execute("CREATE SCHEMA IF NOT EXISTS attendance")

    # ------------------------------------------------------------------
    # attendance.punch_settings (branch-scoped configuration)
    # ------------------------------------------------------------------
    op.create_table(
        "punch_settings",
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "allow_multiple_sessions_per_day",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("max_session_hours", sa.Integer(), nullable=False, server_default=sa.text("16")),
        # v1 placeholder: later we can enforce geo-fence / required GPS.
        sa.Column("require_location", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("geo_fence_json", psql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("tenant_id", "branch_id", name="pk_punch_settings"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_punch_settings_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_punch_settings_branch_id",
            ondelete="CASCADE",
        ),
        schema="attendance",
    )
    _create_updated_at_trigger("attendance", "punch_settings")

    # ------------------------------------------------------------------
    # attendance.punches (immutable punch events)
    # ------------------------------------------------------------------
    op.create_table(
        "punches",
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
        sa.Column("ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("source", sa.Text(), nullable=False),
        # Future-proof references (biometric device id, CCTV job id, import batch id, etc.)
        sa.Column("source_ref_type", sa.Text(), nullable=True),
        sa.Column("source_ref_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("meta", psql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("action in ('IN','OUT')", name="ck_punches_action"),
        sa.CheckConstraint(
            "source in ('MANUAL_WEB','MANUAL_MOBILE','SYSTEM','BIOMETRIC','CCTV','IMPORT')",
            name="ck_punches_source",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_punches_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_punches_branch_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_punches_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["iam.users.id"],
            name="fk_punches_created_by_user_id",
            ondelete="SET NULL",
        ),
        schema="attendance",
    )
    # Alembic's op.create_index does not express DESC order cleanly across
    # dialects. We use raw SQL for Postgres to keep the desired sort order.
    op.execute(
        sa.text(
            """
            CREATE INDEX ix_punches_employee_ts
            ON attendance.punches (tenant_id, employee_id, ts DESC)
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE INDEX ix_punches_branch_ts
            ON attendance.punches (tenant_id, branch_id, ts DESC)
            """
        )
    )
    op.create_index(
        "uq_punches_idempotency",
        "punches",
        ["tenant_id", "employee_id", "idempotency_key"],
        unique=True,
        schema="attendance",
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # attendance.work_sessions (paired sessions derived from punches)
    # ------------------------------------------------------------------
    op.create_table(
        "work_sessions",
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
        sa.Column("business_date", sa.Date(), nullable=False),
        sa.Column("start_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_ts", sa.DateTime(timezone=True), nullable=True),
        sa.Column("minutes", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("start_punch_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("end_punch_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source_start", sa.Text(), nullable=False),
        sa.Column("source_end", sa.Text(), nullable=True),
        sa.Column("anomaly_code", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint(
            "status in ('OPEN','CLOSED','AUTO_CLOSED')",
            name="ck_work_sessions_status",
        ),
        sa.CheckConstraint(
            "source_start in ('MANUAL_WEB','MANUAL_MOBILE','SYSTEM','BIOMETRIC','CCTV','IMPORT')",
            name="ck_work_sessions_source_start",
        ),
        sa.CheckConstraint(
            "(source_end IS NULL) OR (source_end in ('MANUAL_WEB','MANUAL_MOBILE','SYSTEM','BIOMETRIC','CCTV','IMPORT'))",
            name="ck_work_sessions_source_end",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_work_sessions_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_work_sessions_branch_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_work_sessions_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["start_punch_id"],
            ["attendance.punches.id"],
            name="fk_work_sessions_start_punch_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["end_punch_id"],
            ["attendance.punches.id"],
            name="fk_work_sessions_end_punch_id",
            ondelete="RESTRICT",
        ),
        schema="attendance",
    )

    op.create_index(
        "uq_work_sessions_open",
        "work_sessions",
        ["tenant_id", "employee_id"],
        unique=True,
        schema="attendance",
        postgresql_where=sa.text("status = 'OPEN'"),
    )
    op.create_index(
        "ix_work_sessions_employee_day",
        "work_sessions",
        ["tenant_id", "employee_id", "business_date"],
        unique=False,
        schema="attendance",
    )
    op.create_index(
        "ix_work_sessions_branch_day",
        "work_sessions",
        ["tenant_id", "branch_id", "business_date"],
        unique=False,
        schema="attendance",
    )
    _create_updated_at_trigger("attendance", "work_sessions")

    # ------------------------------------------------------------------
    # attendance.attendance_daily extensions (derived; supports punch pipeline)
    # ------------------------------------------------------------------
    op.add_column(
        "attendance_daily",
        sa.Column("source_breakdown", psql.JSONB(), nullable=True),
        schema="attendance",
    )
    op.add_column(
        "attendance_daily",
        sa.Column("has_open_session", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        schema="attendance",
    )


def downgrade() -> None:
    op.drop_column("attendance_daily", "has_open_session", schema="attendance")
    op.drop_column("attendance_daily", "source_breakdown", schema="attendance")

    op.drop_index("ix_work_sessions_branch_day", table_name="work_sessions", schema="attendance")
    op.drop_index("ix_work_sessions_employee_day", table_name="work_sessions", schema="attendance")
    op.drop_index("uq_work_sessions_open", table_name="work_sessions", schema="attendance")
    op.drop_table("work_sessions", schema="attendance")

    op.drop_index("uq_punches_idempotency", table_name="punches", schema="attendance")
    op.drop_index("ix_punches_branch_ts", table_name="punches", schema="attendance")
    op.drop_index("ix_punches_employee_ts", table_name="punches", schema="attendance")
    op.drop_table("punches", schema="attendance")

    op.drop_table("punch_settings", schema="attendance")
