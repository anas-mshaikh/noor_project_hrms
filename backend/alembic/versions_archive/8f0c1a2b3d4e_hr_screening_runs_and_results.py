"""hr screening runs + results (phase 3)

Revision ID: 8f0c1a2b3d4e
Revises: 5d9a1b7c2e34
Create Date: 2026-01-22

Phase 3 HR module additions (ONLY):
- Add `hr_screening_runs` to track an async retrieve+rerank pipeline per opening.
- Add `hr_screening_results` to persist ranked resume results (immutable per run).

Important:
- This is intentionally NOT reusing the CCTV `jobs` table/routes.
- All HR async work remains on the RQ queue named "hr".
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "8f0c1a2b3d4e"
down_revision = "5d9a1b7c2e34"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------
    # Async run record (store-scoped, opening-scoped)
    # -----------------------------
    op.create_table(
        "hr_screening_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("opening_id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        # QUEUED|RUNNING|DONE|FAILED|CANCELLED
        sa.Column("status", sa.String(length=16), nullable=False, server_default="QUEUED"),
        # Run configuration (view types, pool sizes, etc).
        sa.Column(
            "config_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Model version metadata (embed + rerank).
        sa.Column(
            "model_versions_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("rq_job_id", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("progress_total", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("progress_done", sa.Integer(), nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["opening_id"], ["hr_openings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hr_screening_runs_opening_id",
        "hr_screening_runs",
        ["opening_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_screening_runs_store_id",
        "hr_screening_runs",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_screening_runs_status",
        "hr_screening_runs",
        ["status"],
        unique=False,
    )
    op.create_index(
        "ix_hr_screening_runs_created_at",
        "hr_screening_runs",
        ["created_at"],
        unique=False,
    )

    # -----------------------------
    # Ranked results (immutable per run)
    # -----------------------------
    op.create_table(
        "hr_screening_results",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("resume_id", sa.UUID(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("final_score", sa.Float(), nullable=False),
        sa.Column("rerank_score", sa.Float(), nullable=True),
        sa.Column("retrieval_score", sa.Float(), nullable=True),
        sa.Column("best_view_type", sa.String(length=16), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["run_id"], ["hr_screening_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["resume_id"], ["hr_resumes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("run_id", "resume_id"),
    )
    op.create_index(
        "ix_hr_screening_results_run_id",
        "hr_screening_results",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_screening_results_run_rank",
        "hr_screening_results",
        ["run_id", "rank"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_hr_screening_results_run_rank", table_name="hr_screening_results")
    op.drop_index("ix_hr_screening_results_run_id", table_name="hr_screening_results")
    op.drop_table("hr_screening_results")

    op.drop_index("ix_hr_screening_runs_created_at", table_name="hr_screening_runs")
    op.drop_index("ix_hr_screening_runs_status", table_name="hr_screening_runs")
    op.drop_index("ix_hr_screening_runs_store_id", table_name="hr_screening_runs")
    op.drop_index("ix_hr_screening_runs_opening_id", table_name="hr_screening_runs")
    op.drop_table("hr_screening_runs")

