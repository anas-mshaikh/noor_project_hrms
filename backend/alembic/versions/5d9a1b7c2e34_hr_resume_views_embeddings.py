"""hr resume views + embeddings (phase 2)

Revision ID: 5d9a1b7c2e34
Revises: 3c8d1f2a9b10
Create Date: 2026-01-21

Phase 2 HR module additions (ONLY):
- Add `hr_resume_views` table to store multiple text "views" per resume + a pgvector embedding.
- Add embedding status fields on `hr_resumes` for easy UI/status inspection.

Notes:
- We use pgvector `Vector(dim=1024)` because BGE-M3 outputs 1024-d embeddings.
- We keep an IVFFLAT index for cosine distance ready for scale, but the system still works
  without it (small datasets can use sequential scans).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers, used by Alembic.
revision = "5d9a1b7c2e34"
down_revision = "3c8d1f2a9b10"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------
    # Per-resume text views + embeddings
    # -----------------------------
    op.create_table(
        "hr_resume_views",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("resume_id", sa.UUID(), nullable=False),
        sa.Column("view_type", sa.String(length=16), nullable=False),
        # Hash of the exact text used for embedding (after normalization/truncation).
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        # BGE-M3: 1024-d vector.
        sa.Column("embedding", Vector(dim=1024), nullable=True),
        # Optional: store a cheap token estimate for debugging.
        sa.Column("tokens", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["resume_id"], ["hr_resumes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("resume_id", "view_type", name="uq_hr_resume_views_resume_type"),
    )

    op.create_index(
        "ix_hr_resume_views_resume_id",
        "hr_resume_views",
        ["resume_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_resume_views_view_type",
        "hr_resume_views",
        ["view_type"],
        unique=False,
    )
    op.create_index(
        "ix_hr_resume_views_updated_at",
        "hr_resume_views",
        ["updated_at"],
        unique=False,
    )

    # Optional vector index (recommended once you have enough rows).
    # NOTE: IVFFLAT requires ANALYZE and enough rows to be beneficial.
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_hr_resume_views_embedding_ivfflat "
        "ON hr_resume_views USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100)"
    )

    # -----------------------------
    # Resume embedding status (UI-friendly)
    # -----------------------------
    op.add_column(
        "hr_resumes",
        sa.Column(
            "embedding_status",
            sa.String(length=16),
            server_default="PENDING",
            nullable=False,
        ),
    )
    op.add_column("hr_resumes", sa.Column("embedding_error", sa.Text(), nullable=True))
    op.add_column(
        "hr_resumes", sa.Column("embedded_at", sa.DateTime(timezone=True), nullable=True)
    )

    op.create_index(
        "ix_hr_resumes_embedding_status",
        "hr_resumes",
        ["embedding_status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_hr_resumes_embedding_status", table_name="hr_resumes")
    op.drop_column("hr_resumes", "embedded_at")
    op.drop_column("hr_resumes", "embedding_error")
    op.drop_column("hr_resumes", "embedding_status")

    op.execute("DROP INDEX IF EXISTS ix_hr_resume_views_embedding_ivfflat")
    op.drop_index("ix_hr_resume_views_updated_at", table_name="hr_resume_views")
    op.drop_index("ix_hr_resume_views_view_type", table_name="hr_resume_views")
    op.drop_index("ix_hr_resume_views_resume_id", table_name="hr_resume_views")
    op.drop_table("hr_resume_views")

