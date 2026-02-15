"""Workflow: add workflow.notifications table (in-app notifications).

Revision ID: 571e947ad55d
Revises: a2ce7edbde24
Create Date: 2026-02-12

Milestone 1 adds in-app notifications using workflow.notification_outbox as the
producer mechanism and workflow.notifications as the user-facing store.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "571e947ad55d"
down_revision = "a2ce7edbde24"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("recipient_user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("outbox_id", UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=True),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("action_url", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_notifications_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["recipient_user_id"],
            ["iam.users.id"],
            name="fk_notifications_recipient_user_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["outbox_id"],
            ["workflow.notification_outbox.id"],
            name="fk_notifications_outbox_id",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("outbox_id", name="uq_notifications_outbox_id"),
        schema="workflow",
    )

    # Note: a btree index can be scanned backwards, so we don't need DESC here.
    op.create_index(
        "ix_notifications_recipient_created_at",
        "notifications",
        ["tenant_id", "recipient_user_id", "created_at"],
        unique=False,
        schema="workflow",
    )
    op.create_index(
        "ix_notifications_recipient_read_at",
        "notifications",
        ["tenant_id", "recipient_user_id", "read_at"],
        unique=False,
        schema="workflow",
    )


def downgrade() -> None:
    op.drop_table("notifications", schema="workflow")

