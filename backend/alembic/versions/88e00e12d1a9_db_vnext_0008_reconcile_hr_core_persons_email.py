"""DB vNext (0008): reconcile hr_core.persons.email for drifted dev DBs.

Revision ID: 88e00e12d1a9
Revises: 8c028d85bff3
Create Date: 2026-01-30

Why this exists:
- Some dev DB volumes may have applied an older version of DB vNext 0001 that
  created `hr_core.persons` without the optional `email` column.
- DB vNext treats `hr_core.persons` as the canonical person master, and APIs/
  smoke tests expect the column to exist.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "88e00e12d1a9"
down_revision = "8c028d85bff3"
branch_labels = None
depends_on = None


def _table_exists(conn, fqtn: str) -> bool:
    return conn.execute(sa.text("SELECT to_regclass(:fqtn)"), {"fqtn": fqtn}).scalar() is not None


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
    for fqtn in ("tenancy.tenants", "hr_core.persons"):
        if not _table_exists(conn, fqtn):
            raise RuntimeError(
                f"Expected DB vNext table {fqtn} to exist, but it was not found. "
                "Refusing to run reconciliation migration."
            )

    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    if not _column_exists(conn, "hr_core", "persons", "email"):
        op.execute("ALTER TABLE hr_core.persons ADD COLUMN email citext NULL")


def downgrade() -> None:
    raise NotImplementedError("DB vNext migrations are forward-only after hard cutover.")

