"""hr ats pipeline stages + applications (phase 5)

Revision ID: 6a1c3d9e4f20
Revises: 0d4b2a8f9c61
Create Date: 2026-01-22

Phase 5 HR module additions (ONLY):
- Add a minimal ATS (Applicant Tracking System) layer on top of:
    - hr_openings (Phase 1)
    - hr_resumes (Phase 1)
    - hr_screening_runs/results (Phase 3)

Key design decision for MVP:
- We do NOT introduce a "candidate identity" table yet.
- Each resume is treated as the applicant (1 resume = 1 application).

Important constraints:
- This does NOT touch CCTV jobs tables or endpoints.
- No background tasks are required for ATS Phase 5 (pure CRUD).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "6a1c3d9e4f20"
down_revision = "0d4b2a8f9c61"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------
    # Pipeline stages per opening
    # -----------------------------
    op.create_table(
        "hr_pipeline_stages",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("opening_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_terminal", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["opening_id"], ["hr_openings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("opening_id", "name", name="uq_hr_pipeline_stages_opening_name"),
    )
    op.create_index(
        "ix_hr_pipeline_stages_opening_sort",
        "hr_pipeline_stages",
        ["opening_id", "sort_order"],
        unique=False,
    )

    # -----------------------------
    # Applications (resume == applicant)
    # -----------------------------
    op.create_table(
        "hr_applications",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("opening_id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("resume_id", sa.UUID(), nullable=False),
        sa.Column("stage_id", sa.UUID(), nullable=True),
        # ACTIVE|REJECTED|HIRED (MVP)
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        # Optional: which ScreeningRun produced this application (useful for audit).
        sa.Column("source_run_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(["opening_id"], ["hr_openings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resume_id"], ["hr_resumes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["stage_id"], ["hr_pipeline_stages.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["source_run_id"], ["hr_screening_runs.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("opening_id", "resume_id", name="uq_hr_applications_opening_resume"),
    )
    op.create_index(
        "ix_hr_applications_opening_id",
        "hr_applications",
        ["opening_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_applications_stage_id",
        "hr_applications",
        ["stage_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_applications_store_id",
        "hr_applications",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_applications_status",
        "hr_applications",
        ["status"],
        unique=False,
    )

    # -----------------------------
    # Notes per application
    # -----------------------------
    op.create_table(
        "hr_application_notes",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=False),
        # Optional for future auth/audit: who wrote this note.
        sa.Column("author_id", sa.UUID(), nullable=True),
        sa.Column("note", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["application_id"], ["hr_applications.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hr_application_notes_application_created_at",
        "hr_application_notes",
        ["application_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hr_application_notes_application_created_at",
        table_name="hr_application_notes",
    )
    op.drop_table("hr_application_notes")

    op.drop_index("ix_hr_applications_status", table_name="hr_applications")
    op.drop_index("ix_hr_applications_store_id", table_name="hr_applications")
    op.drop_index("ix_hr_applications_stage_id", table_name="hr_applications")
    op.drop_index("ix_hr_applications_opening_id", table_name="hr_applications")
    op.drop_table("hr_applications")

    op.drop_index("ix_hr_pipeline_stages_opening_sort", table_name="hr_pipeline_stages")
    op.drop_table("hr_pipeline_stages")

