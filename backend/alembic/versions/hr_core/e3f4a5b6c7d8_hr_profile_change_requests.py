"""HR Core: profile change requests (Milestone 6).

Revision ID: e3f4a5b6c7d8
Revises: d2c1a8e3b4f5
Create Date: 2026-02-19

This migration introduces a first-class business record for employee profile
change requests:
- ESS submits a change_set (JSONB) and a workflow request (HR_PROFILE_CHANGE)
  drives approval.
- On workflow terminal approval, a domain hook applies the changes to hr_core.*
  inside the same DB transaction as the workflow transition.

Notes:
- Tenant isolation is enforced at the DB level via tenant_id columns and FKs.
- Idempotency is enforced with a partial unique index on
  (tenant_id, employee_id, idempotency_key) where idempotency_key is not null.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql as psql


# revision identifiers, used by Alembic.
revision = "e3f4a5b6c7d8"
down_revision = "d2c1a8e3b4f5"
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
    """Apply schema changes."""

    # Hard dependency: baseline creates public.set_updated_at().
    conn = op.get_bind()
    fn = conn.execute(
        sa.text("SELECT to_regprocedure('public.set_updated_at()')")
    ).scalar()
    if fn is None:
        raise RuntimeError(
            "Missing required function public.set_updated_at(); run baseline first."
        )

    op.create_table(
        "profile_change_requests",
        sa.Column(
            "id",
            psql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("tenant_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_by_user_id", psql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'PENDING'"),
        ),
        sa.Column("workflow_request_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column("change_set", psql.JSONB(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by_user_id", psql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "status in ('PENDING','APPROVED','REJECTED','CANCELED')",
            name="ck_profile_change_requests_status",
        ),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenancy.tenants.id"],
            name="fk_profile_change_requests_tenant_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["hr_core.employees.id"],
            name="fk_profile_change_requests_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["iam.users.id"],
            name="fk_profile_change_requests_created_by_user_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["workflow_request_id"],
            ["workflow.requests.id"],
            name="fk_profile_change_requests_workflow_request_id",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["decided_by_user_id"],
            ["iam.users.id"],
            name="fk_profile_change_requests_decided_by_user_id",
            ondelete="SET NULL",
        ),
        schema="hr_core",
    )

    # Idempotency unique index (partial).
    op.create_index(
        "uq_profile_change_requests_idempotency",
        "profile_change_requests",
        ["tenant_id", "employee_id", "idempotency_key"],
        unique=True,
        schema="hr_core",
        postgresql_where=sa.text("idempotency_key IS NOT NULL"),
    )

    # Read/list query helper index.
    op.create_index(
        "ix_profile_change_requests_employee_created_at",
        "profile_change_requests",
        ["tenant_id", "employee_id", "created_at"],
        unique=False,
        schema="hr_core",
    )

    _create_updated_at_trigger("hr_core", "profile_change_requests")


def downgrade() -> None:
    """Downgrade schema changes."""

    op.drop_index(
        "ix_profile_change_requests_employee_created_at",
        table_name="profile_change_requests",
        schema="hr_core",
    )
    op.drop_index(
        "uq_profile_change_requests_idempotency",
        table_name="profile_change_requests",
        schema="hr_core",
    )
    op.drop_table("profile_change_requests", schema="hr_core")
