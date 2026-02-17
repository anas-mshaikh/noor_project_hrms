"""Imports: make datasets + month_state branch-scoped.

Revision ID: afa169e50ce8
Revises: 571e947ad55d
Create Date: 2026-02-12

Milestone 1 removes legacy "store" concepts and standardizes on branch scope.

Changes:
- Make imports.datasets uniqueness scoped to (tenant_id, branch_id, month_key, checksum)
  so branches/tenants can upload identical files without cross-scope conflicts.
- Make imports.month_state branch-scoped with composite PK:
    (tenant_id, branch_id, month_key)
  and enforce NOT NULL tenant_id/branch_id.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "afa169e50ce8"
down_revision = "571e947ad55d"
branch_labels = None
depends_on = None


def _column_exists(conn, schema: str, table: str, column: str) -> bool:
    return (
        conn.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = :table
                  AND column_name = :column
                """
            ),
            {"schema": schema, "table": table, "column": column},
        ).first()
        is not None
    )


def upgrade() -> None:
    conn = op.get_bind()

    # ------------------------------------------------------------------
    # imports.datasets: scoped uniqueness (tenant + branch + month + checksum)
    # ------------------------------------------------------------------
    # Drop the old global constraint if present.
    op.execute("ALTER TABLE imports.datasets DROP CONSTRAINT IF EXISTS uq_datasets_month_checksum")
    op.execute("ALTER TABLE imports.datasets DROP CONSTRAINT IF EXISTS uq_datasets_tenant_branch_month_checksum")

    op.execute(
        """
        ALTER TABLE imports.datasets
        ADD CONSTRAINT uq_datasets_tenant_branch_month_checksum
        UNIQUE (tenant_id, branch_id, month_key, checksum)
        """
    )

    # ------------------------------------------------------------------
    # imports.month_state: add branch_id + composite PK
    # ------------------------------------------------------------------
    if not _column_exists(conn, "imports", "month_state", "branch_id"):
        op.add_column(
            "month_state",
            sa.Column("branch_id", UUID(as_uuid=True), nullable=True),
            schema="imports",
        )

    # Best-effort backfill from the published dataset pointer.
    op.execute(
        """
        UPDATE imports.month_state m
        SET tenant_id = d.tenant_id,
            branch_id = d.branch_id
        FROM imports.datasets d
        WHERE d.id = m.published_dataset_id
          AND (m.tenant_id IS NULL OR m.branch_id IS NULL)
        """
    )

    # Rows without a published dataset cannot be scoped; drop them (dev cutover).
    op.execute(
        """
        DELETE FROM imports.month_state
        WHERE published_dataset_id IS NULL
           OR tenant_id IS NULL
           OR branch_id IS NULL
        """
    )

    op.execute("ALTER TABLE imports.month_state ALTER COLUMN tenant_id SET NOT NULL")
    op.execute("ALTER TABLE imports.month_state ALTER COLUMN branch_id SET NOT NULL")

    # Ensure branch_id FK (tenant_id FK was added in DB vNext 0009 but is nullable there).
    op.execute("ALTER TABLE imports.month_state DROP CONSTRAINT IF EXISTS fk_month_state_branch_id")
    op.create_foreign_key(
        "fk_month_state_branch_id",
        "month_state",
        "branches",
        ["branch_id"],
        ["id"],
        source_schema="imports",
        referent_schema="tenancy",
        ondelete="CASCADE",
    )

    # Replace the legacy PK(month_key) with PK(tenant_id, branch_id, month_key).
    op.execute("ALTER TABLE imports.month_state DROP CONSTRAINT IF EXISTS month_state_pkey")
    op.execute("ALTER TABLE imports.month_state DROP CONSTRAINT IF EXISTS pk_month_state")
    op.create_primary_key(
        "pk_month_state",
        "month_state",
        ["tenant_id", "branch_id", "month_key"],
        schema="imports",
    )


def downgrade() -> None:
    raise NotImplementedError("Milestone 1 branch-first imports scope is forward-only.")

