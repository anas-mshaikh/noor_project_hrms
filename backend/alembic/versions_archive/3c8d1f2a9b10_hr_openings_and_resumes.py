"""hr openings + resumes (phase 1)

Revision ID: 3c8d1f2a9b10
Revises: 2a4f8b8f6e21
Create Date: 2026-01-19

Phase 1 HR module (ONLY):
- Hiring "Openings" (store-scoped)
- Resume uploads per opening (local file storage)
- Background parsing via RQ + Unstructured (stored artifacts on disk)

We use an `hr_` prefix to avoid collisions with existing CCTV/Imports tables.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "3c8d1f2a9b10"
down_revision = "2a4f8b8f6e21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------
    # Openings (store-scoped)
    # -----------------------------
    op.create_table(
        "hr_openings",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("jd_text", sa.Text(), nullable=False),
        sa.Column(
            "requirements_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_openings_store_id", "hr_openings", ["store_id"], unique=False)
    op.create_index("ix_hr_openings_status", "hr_openings", ["status"], unique=False)

    # -----------------------------
    # Optional batches (simple grouping for uploads)
    # -----------------------------
    op.create_table(
        "hr_resume_batches",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("opening_id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("total_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["opening_id"], ["hr_openings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hr_resume_batches_opening_id",
        "hr_resume_batches",
        ["opening_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_resume_batches_store_id",
        "hr_resume_batches",
        ["store_id"],
        unique=False,
    )

    # -----------------------------
    # Resumes
    # -----------------------------
    op.create_table(
        "hr_resumes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("opening_id", sa.UUID(), nullable=False),
        # Denormalized store_id makes listing/filtering cheaper (no join needed).
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("batch_id", sa.UUID(), nullable=True),
        sa.Column("original_filename", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=False),
        sa.Column("parsed_path", sa.Text(), nullable=True),
        sa.Column("clean_text_path", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=16),
            nullable=False,
            server_default="UPLOADED",
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("rq_job_id", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["opening_id"], ["hr_openings.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["batch_id"], ["hr_resume_batches.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hr_resumes_opening_id", "hr_resumes", ["opening_id"], unique=False)
    op.create_index("ix_hr_resumes_store_id", "hr_resumes", ["store_id"], unique=False)
    op.create_index("ix_hr_resumes_status", "hr_resumes", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_hr_resumes_status", table_name="hr_resumes")
    op.drop_index("ix_hr_resumes_store_id", table_name="hr_resumes")
    op.drop_index("ix_hr_resumes_opening_id", table_name="hr_resumes")
    op.drop_table("hr_resumes")

    op.drop_index("ix_hr_resume_batches_store_id", table_name="hr_resume_batches")
    op.drop_index("ix_hr_resume_batches_opening_id", table_name="hr_resume_batches")
    op.drop_table("hr_resume_batches")

    op.drop_index("ix_hr_openings_status", table_name="hr_openings")
    op.drop_index("ix_hr_openings_store_id", table_name="hr_openings")
    op.drop_table("hr_openings")

