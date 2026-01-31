"""DB vNext (0007): reconcile iam.users.email for drifted dev DBs.

Revision ID: 8c028d85bff3
Revises: d5a2c6e8f1b3
Create Date: 2026-01-30

Why this exists:
- Some dev DB volumes may have applied an earlier version of DB vNext 0001 that
  created `iam.users` without the `email` column.
- Alembic will not re-run edited migrations, so we add a forward-only corrective
  migration to bring the canonical vNext table back to spec.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "8c028d85bff3"
down_revision = "d5a2c6e8f1b3"
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

    # Safety: ensure this is a DB vNext database before altering anything.
    required_tables = [
        ("tenancy", "tenants"),
        ("iam", "users"),
        ("hr_core", "employees"),
        ("workflow", "requests"),
        ("dms", "documents"),
    ]
    for schema, table in required_tables:
        exists = conn.execute(sa.text("SELECT to_regclass(:name)"), {"name": f"{schema}.{table}"}).scalar()
        if exists is None:
            raise RuntimeError(
                f"Expected DB vNext table {schema}.{table} to exist, but it was not found. "
                "Refusing to run reconciliation migration."
            )

    # Ensure citext exists (email is CITEXT in the canonical schema).
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    # If a dev DB volume drifted, these columns may be missing.
    # Keep reconciliation focused on the contract used by auth/RBAC and the smoke test.
    if not _column_exists(conn, "iam", "users", "deleted_at"):
        op.execute("ALTER TABLE iam.users ADD COLUMN deleted_at timestamptz NULL")

    if not _column_exists(conn, "iam", "users", "email"):
        # Add the column as nullable first, backfill, then make it NOT NULL.
        op.execute("ALTER TABLE iam.users ADD COLUMN email citext")
        op.execute(
            """
            UPDATE iam.users
            SET email = 'user+' || id::text || '@example.invalid'
            WHERE email IS NULL
            """
        )
        op.execute("ALTER TABLE iam.users ALTER COLUMN email SET NOT NULL")
    else:
        # Ensure NOT NULL for email (vNext contract).
        op.execute(
            """
            UPDATE iam.users
            SET email = 'user+' || id::text || '@example.invalid'
            WHERE email IS NULL
            """
        )
        op.execute("ALTER TABLE iam.users ALTER COLUMN email SET NOT NULL")

    # Ensure the canonical partial-unique constraint exists for non-deleted users.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email_not_deleted
        ON iam.users (email)
        WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:
    # Destructive reconciliation; keep downgrade explicit.
    raise NotImplementedError("DB vNext migrations are forward-only after hard cutover.")
