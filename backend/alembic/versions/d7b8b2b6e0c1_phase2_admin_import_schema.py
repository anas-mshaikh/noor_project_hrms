"""phase2 admin import schema

Revision ID: d7b8b2b6e0c1
Revises: a1e5035b95d5
Create Date: 2026-01-14

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d7b8b2b6e0c1"
down_revision: Union[str, Sequence[str], None] = "a1e5035b95d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "datasets",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("month_key", sa.String(length=16), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("uploaded_by", sa.String(length=200), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default="VALIDATING",
            nullable=False,
        ),
        sa.Column(
            "sync_status",
            sa.String(length=16),
            server_default="DISABLED",
            nullable=False,
        ),
        sa.Column("raw_file_path", sa.Text(), nullable=True),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.CheckConstraint(
            "status in ('VALIDATING','READY','FAILED')", name="ck_datasets_status"
        ),
        sa.CheckConstraint(
            "sync_status in ('DISABLED','PENDING','SYNCED','FAILED')",
            name="ck_datasets_sync_status",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("month_key", "checksum", name="uq_datasets_month_checksum"),
    )
    op.create_index(op.f("ix_datasets_month_key"), "datasets", ["month_key"], unique=False)

    op.create_table(
        "month_state",
        sa.Column("month_key", sa.String(length=16), nullable=False),
        sa.Column("published_dataset_id", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["published_dataset_id"], ["datasets.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("month_key"),
    )

    op.create_table(
        "salesmen",
        sa.Column("salesman_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("department", sa.String(length=200), nullable=True),
        sa.Column(
            "active",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("salesman_id"),
    )

    op.create_table(
        "pos_summary",
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("salesman_id", sa.String(length=128), nullable=False),
        sa.Column("qty", sa.Numeric(), nullable=True),
        sa.Column("net_sales", sa.Numeric(), nullable=True),
        sa.Column("bills", sa.Integer(), nullable=True),
        sa.Column("customers", sa.Integer(), nullable=True),
        sa.Column("return_customers", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["salesman_id"], ["salesmen.salesman_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("dataset_id", "salesman_id"),
    )

    op.create_table(
        "attendance_summary",
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("salesman_id", sa.String(length=128), nullable=False),
        sa.Column("present", sa.Integer(), nullable=True),
        sa.Column("absent", sa.Integer(), nullable=True),
        sa.Column("work_minutes", sa.Integer(), nullable=True),
        sa.Column("stocking_done", sa.Integer(), nullable=True),
        sa.Column("stocking_missed", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["salesman_id"], ["salesmen.salesman_id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("dataset_id", "salesman_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("attendance_summary")
    op.drop_table("pos_summary")
    op.drop_table("salesmen")
    op.drop_table("month_state")
    op.drop_index(op.f("ix_datasets_month_key"), table_name="datasets")
    op.drop_table("datasets")

