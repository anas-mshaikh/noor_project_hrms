"""add store_id to datasets

Revision ID: 9c2f9b9d8e73
Revises: d7b8b2b6e0c1
Create Date: 2026-01-16
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "9c2f9b9d8e73"
down_revision = "d7b8b2b6e0c1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "datasets",
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_index(op.f("ix_datasets_store_id"), "datasets", ["store_id"])
    op.create_foreign_key(
        "fk_datasets_store_id",
        "datasets",
        "stores",
        ["store_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_datasets_store_id", "datasets", type_="foreignkey")
    op.drop_index(op.f("ix_datasets_store_id"), table_name="datasets")
    op.drop_column("datasets", "store_id")
