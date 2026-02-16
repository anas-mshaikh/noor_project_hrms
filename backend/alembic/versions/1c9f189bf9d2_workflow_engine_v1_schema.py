"""Workflow v1: schema extensions (assignees, events, idempotency, outbox dedupe).

Revision ID: 1c9f189bf9d2
Revises: f6c2951ba7d5
Create Date: 2026-02-16

Milestone 2 introduces a reusable workflow engine built on the existing DB vNext
workflow tables. This migration is additive and aligns to the current schema:
- Adds requester/user linkage + idempotency fields on workflow.requests.
- Supports multi-assignee ROLE steps via workflow.request_step_assignees.
- Adds workflow.request_events for an audit-friendly timeline.
- Adds note on workflow.request_attachments.
- Adds definition metadata (code/version) and step metadata (scope_mode/fallback_role_code).
- Adds notification_outbox.dedupe_key for idempotent notification producers.

Notes:
- We avoid renaming existing columns to keep DB compatibility with vNext 0001.
- No production data; safe hardening is acceptable.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID


# revision identifiers, used by Alembic.
revision = "1c9f189bf9d2"
down_revision = "f6c2951ba7d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # workflow.requests: requester/user linkage + optional entity refs + idempotency
    # ------------------------------------------------------------------
    op.add_column("requests", sa.Column("created_by_user_id", UUID(as_uuid=True), nullable=True), schema="workflow")
    op.add_column("requests", sa.Column("subject_employee_id", UUID(as_uuid=True), nullable=True), schema="workflow")
    op.add_column("requests", sa.Column("entity_type", sa.Text(), nullable=True), schema="workflow")
    op.add_column("requests", sa.Column("entity_id", UUID(as_uuid=True), nullable=True), schema="workflow")
    op.add_column("requests", sa.Column("idempotency_key", sa.Text(), nullable=True), schema="workflow")

    op.create_foreign_key(
        "fk_requests_created_by_user_id",
        source_table="requests",
        referent_table="users",
        local_cols=["created_by_user_id"],
        remote_cols=["id"],
        source_schema="workflow",
        referent_schema="iam",
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_requests_subject_employee_id",
        source_table="requests",
        referent_table="employees",
        local_cols=["subject_employee_id"],
        remote_cols=["id"],
        source_schema="workflow",
        referent_schema="hr_core",
        ondelete="SET NULL",
    )

    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_requests_tenant_creator_idempotency
        ON workflow.requests (tenant_id, created_by_user_id, idempotency_key)
        WHERE created_by_user_id IS NOT NULL AND idempotency_key IS NOT NULL
        """
    )

    # ------------------------------------------------------------------
    # workflow.request_steps: allow ROLE steps (multi-assignee) and store resolved metadata
    # ------------------------------------------------------------------
    op.alter_column(
        "request_steps",
        "approver_user_id",
        existing_type=UUID(as_uuid=True),
        nullable=True,
        schema="workflow",
    )
    op.add_column("request_steps", sa.Column("assignee_type", sa.Text(), nullable=True), schema="workflow")
    op.add_column("request_steps", sa.Column("assignee_role_code", sa.Text(), nullable=True), schema="workflow")
    op.add_column("request_steps", sa.Column("assignee_user_id", UUID(as_uuid=True), nullable=True), schema="workflow")
    op.create_foreign_key(
        "fk_request_steps_assignee_user_id",
        source_table="request_steps",
        referent_table="users",
        local_cols=["assignee_user_id"],
        remote_cols=["id"],
        source_schema="workflow",
        referent_schema="iam",
        ondelete="SET NULL",
    )

    # ------------------------------------------------------------------
    # workflow.request_step_assignees: multi-assignee join (tenant-scoped)
    # ------------------------------------------------------------------
    op.create_table(
        "request_step_assignees",
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("step_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_request_step_assignees_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["step_id"],
            ["workflow.request_steps.id"],
            name="fk_request_step_assignees_step_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["iam.users.id"],
            name="fk_request_step_assignees_user_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("step_id", "user_id", name="pk_request_step_assignees"),
        schema="workflow",
    )
    op.create_index(
        "ix_request_step_assignees_tenant_user_step",
        "request_step_assignees",
        ["tenant_id", "user_id", "step_id"],
        unique=False,
        schema="workflow",
    )

    # ------------------------------------------------------------------
    # workflow.request_events: request timeline/events (tenant-scoped)
    # ------------------------------------------------------------------
    op.create_table(
        "request_events",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("request_id", UUID(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", UUID(as_uuid=True), nullable=True),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column(
            "data",
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
            name="fk_request_events_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["request_id"],
            ["workflow.requests.id"],
            name="fk_request_events_request_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["iam.users.id"],
            name="fk_request_events_actor_user_id",
            ondelete="SET NULL",
        ),
        schema="workflow",
    )
    op.create_index(
        "ix_request_events_tenant_request_created_at",
        "request_events",
        ["tenant_id", "request_id", "created_at"],
        unique=False,
        schema="workflow",
    )

    # ------------------------------------------------------------------
    # workflow.request_attachments: optional note
    # ------------------------------------------------------------------
    op.add_column("request_attachments", sa.Column("note", sa.Text(), nullable=True), schema="workflow")

    # ------------------------------------------------------------------
    # workflow.workflow_definitions: code/version metadata
    # ------------------------------------------------------------------
    op.add_column("workflow_definitions", sa.Column("code", sa.Text(), nullable=True), schema="workflow")
    op.add_column("workflow_definitions", sa.Column("version", sa.Integer(), nullable=True), schema="workflow")

    # ------------------------------------------------------------------
    # workflow.workflow_definition_steps: scope + manager fallback
    # ------------------------------------------------------------------
    op.add_column(
        "workflow_definition_steps",
        sa.Column("scope_mode", sa.Text(), nullable=False, server_default=sa.text("'TENANT'")),
        schema="workflow",
    )
    op.add_column(
        "workflow_definition_steps",
        sa.Column("fallback_role_code", sa.Text(), nullable=True),
        schema="workflow",
    )

    # ------------------------------------------------------------------
    # workflow.notification_outbox: dedupe key for idempotent producers
    # ------------------------------------------------------------------
    op.add_column("notification_outbox", sa.Column("dedupe_key", sa.Text(), nullable=True), schema="workflow")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_notification_outbox_dedupe
        ON workflow.notification_outbox (tenant_id, channel, dedupe_key)
        WHERE dedupe_key IS NOT NULL
        """
    )


def downgrade() -> None:
    # Best-effort cleanup (dev only).
    op.execute("DROP INDEX IF EXISTS workflow.uq_notification_outbox_dedupe")
    op.drop_column("notification_outbox", "dedupe_key", schema="workflow")

    op.drop_column("workflow_definition_steps", "fallback_role_code", schema="workflow")
    op.drop_column("workflow_definition_steps", "scope_mode", schema="workflow")

    op.drop_column("workflow_definitions", "version", schema="workflow")
    op.drop_column("workflow_definitions", "code", schema="workflow")

    op.drop_column("request_attachments", "note", schema="workflow")

    op.drop_index("ix_request_events_tenant_request_created_at", table_name="request_events", schema="workflow")
    op.drop_table("request_events", schema="workflow")

    op.drop_index(
        "ix_request_step_assignees_tenant_user_step",
        table_name="request_step_assignees",
        schema="workflow",
    )
    op.drop_table("request_step_assignees", schema="workflow")

    op.drop_constraint("fk_request_steps_assignee_user_id", "request_steps", schema="workflow", type_="foreignkey")
    op.drop_column("request_steps", "assignee_user_id", schema="workflow")
    op.drop_column("request_steps", "assignee_role_code", schema="workflow")
    op.drop_column("request_steps", "assignee_type", schema="workflow")
    op.alter_column(
        "request_steps",
        "approver_user_id",
        existing_type=UUID(as_uuid=True),
        nullable=False,
        schema="workflow",
    )

    op.execute("DROP INDEX IF EXISTS workflow.uq_requests_tenant_creator_idempotency")
    op.drop_constraint("fk_requests_subject_employee_id", "requests", schema="workflow", type_="foreignkey")
    op.drop_constraint("fk_requests_created_by_user_id", "requests", schema="workflow", type_="foreignkey")
    op.drop_column("requests", "idempotency_key", schema="workflow")
    op.drop_column("requests", "entity_id", schema="workflow")
    op.drop_column("requests", "entity_type", schema="workflow")
    op.drop_column("requests", "subject_employee_id", schema="workflow")
    op.drop_column("requests", "created_by_user_id", schema="workflow")

