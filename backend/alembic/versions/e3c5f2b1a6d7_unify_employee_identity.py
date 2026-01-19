"""unify employee identity for imports

Revision ID: e3c5f2b1a6d7
Revises: 9c2f9b9d8e73
Create Date: 2026-01-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "e3c5f2b1a6d7"
down_revision = "9c2f9b9d8e73"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Employees: add department and updated_at, plus uniqueness and active index.
    op.add_column(
        "employees",
        sa.Column(
            "department",
            sa.String(length=200),
            server_default="Unknown",
            nullable=False,
        ),
    )
    op.add_column(
        "employees",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    )
    # NOTE:
    # `uq_employees_store_employee_code` is already created in the initial
    # identity migration that creates the `employees` table. On a fresh DB,
    # creating it again will crash with DuplicateTable. So we only create it
    # if it does not already exist.
    conn = op.get_bind()
    exists_constraint = conn.execute(
        text("SELECT 1 FROM pg_constraint WHERE conname = :name"),
        {"name": "uq_employees_store_employee_code"},
    ).first()
    # In some dev DBs we may end up with a leftover unique index (relation) with the
    # same name even if the constraint itself was dropped (or never created).
    # Postgres reports that scenario as:
    #   DuplicateTable: relation "uq_employees_store_employee_code" already exists
    exists_relation = conn.execute(
        text("SELECT to_regclass(:qualified_name)"),
        {"qualified_name": "public.uq_employees_store_employee_code"},
    ).scalar()

    if not exists_constraint and exists_relation is None:
        op.create_unique_constraint(
            "uq_employees_store_employee_code",
            "employees",
            ["store_id", "employee_code"],
        )

    op.create_index(
        "ix_employees_store_active",
        "employees",
        ["store_id", "is_active"],
    )

    # Datasets: store_id must be present and cascade with stores.
    op.execute(
        """
        UPDATE datasets
        SET store_id = (SELECT id FROM stores LIMIT 1)
        WHERE store_id IS NULL AND (SELECT COUNT(*) FROM stores) = 1
        """
    )
    op.drop_constraint("fk_datasets_store_id", "datasets", type_="foreignkey")
    op.alter_column("datasets", "store_id", nullable=False)
    op.create_foreign_key(
        "fk_datasets_store_id",
        "datasets",
        "stores",
        ["store_id"],
        ["id"],
        ondelete="CASCADE",
    )

def downgrade() -> None:
    op.drop_index("ix_employees_store_active", table_name="employees")
    op.drop_constraint(
        "uq_employees_store_employee_code",
        "employees",
        type_="unique",
    )
    op.drop_column("employees", "updated_at")
    op.drop_column("employees", "department")

    op.drop_constraint("fk_datasets_store_id", "datasets", type_="foreignkey")
    op.alter_column("datasets", "store_id", nullable=True)
    op.create_foreign_key(
        "fk_datasets_store_id",
        "datasets",
        "stores",
        ["store_id"],
        ["id"],
        ondelete="SET NULL",
    )
