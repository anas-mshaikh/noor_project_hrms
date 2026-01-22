"""hr screening explanations (phase 4)

Revision ID: 0d4b2a8f9c61
Revises: 8f0c1a2b3d4e
Create Date: 2026-01-22

Phase 4 HR module additions (ONLY):
- Add `hr_screening_explanations` to store structured LLM explanations for top candidates.

Notes:
- Explanations are generated asynchronously via RQ (queue: "hr") so ScreeningRuns are not blocked.
- We store only structured JSON outputs (no raw resume text persisted in DB).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "0d4b2a8f9c61"
down_revision = "8f0c1a2b3d4e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hr_screening_explanations",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("resume_id", sa.UUID(), nullable=False),
        # Optional snapshot: rank at the time the explanation was generated.
        sa.Column("rank", sa.Integer(), nullable=True),
        # Model metadata for audit/debugging.
        sa.Column("model_name", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.Text(), nullable=False),
        # Structured output only (no raw resume text stored).
        sa.Column(
            "explanation_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
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
        "ix_hr_screening_explanations_run_id",
        "hr_screening_explanations",
        ["run_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_screening_explanations_run_created_at",
        "hr_screening_explanations",
        ["run_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hr_screening_explanations_run_created_at",
        table_name="hr_screening_explanations",
    )
    op.drop_index(
        "ix_hr_screening_explanations_run_id",
        table_name="hr_screening_explanations",
    )
    op.drop_table("hr_screening_explanations")

