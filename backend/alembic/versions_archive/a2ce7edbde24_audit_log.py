"""Audit: add audit.audit_log table.

Revision ID: a2ce7edbde24
Revises: 6e4f83bf4ad6
Create Date: 2026-02-12

Milestone 1 introduces audit logging for critical actions (IAM/HR mutations).
This migration creates the `audit` schema and a minimal `audit_log` table.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "a2ce7edbde24"
down_revision = "6e4f83bf4ad6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS audit")

    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "diff_json",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("correlation_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_audit_log_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["iam.users.id"],
            name="fk_audit_log_actor_user_id",
            ondelete="RESTRICT",
        ),
        schema="audit",
    )

    # Note: a btree index can be scanned backwards, so we don't need DESC here.
    op.create_index(
        "ix_audit_log_tenant_created_at",
        "audit_log",
        ["tenant_id", "created_at"],
        unique=False,
        schema="audit",
    )
    op.create_index(
        "ix_audit_log_entity",
        "audit_log",
        ["tenant_id", "entity_type", "entity_id"],
        unique=False,
        schema="audit",
    )


def downgrade() -> None:
    op.drop_table("audit_log", schema="audit")
    op.execute("DROP SCHEMA IF EXISTS audit")

