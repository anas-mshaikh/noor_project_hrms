"""Attendance: add day_overrides table (Leave integration foundation).

Revision ID: a0793d36f998
Revises: 99fce1d9b3c4
Create Date: 2026-02-16

Milestone 3 (Leave) needs a minimal attendance override mechanism to mark days
as ON_LEAVE after workflow approval.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "a0793d36f998"
down_revision = "99fce1d9b3c4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS attendance")

    op.create_table(
        "day_overrides",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("branch_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("source_type", sa.Text(), nullable=False),
        sa.Column("source_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status in ('ON_LEAVE')", name="ck_day_overrides_status"),
        sa.CheckConstraint("source_type in ('LEAVE_REQUEST')", name="ck_day_overrides_source_type"),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_day_overrides_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_day_overrides_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["tenancy.branches.id"],
            name="fk_day_overrides_branch_id",
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint(
            "tenant_id",
            "employee_id",
            "day",
            "source_type",
            "source_id",
            name="uq_day_overrides_unique",
        ),
        schema="attendance",
    )

    op.create_index(
        "ix_day_overrides_employee_day",
        "day_overrides",
        ["tenant_id", "employee_id", "day"],
        unique=False,
        schema="attendance",
    )


def downgrade() -> None:
    op.drop_index("ix_day_overrides_employee_day", table_name="day_overrides", schema="attendance")
    op.drop_table("day_overrides", schema="attendance")

