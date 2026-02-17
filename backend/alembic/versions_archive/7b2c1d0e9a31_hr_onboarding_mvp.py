"""hr onboarding mvp (phase 6)

Revision ID: 7b2c1d0e9a31
Revises: 6a1c3d9e4f20
Create Date: 2026-01-22

Phase 6 HR module additions (ONLY):
- Convert a HIRED ATS application into a real `employees` row (bridge ATS -> attendance world)
- Create onboarding plans + tasks
- Track onboarding document uploads stored locally under `settings.data_dir`

Important constraints:
- This does NOT touch CCTV jobs tables or endpoints.
- Everything is local: Postgres + local disk storage.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "7b2c1d0e9a31"
down_revision = "6a1c3d9e4f20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -----------------------------
    # Link ATS application -> employee
    # -----------------------------
    op.add_column(
        "hr_applications",
        sa.Column("employee_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "hr_applications",
        sa.Column("hired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "hr_applications",
        sa.Column("start_date", sa.Date(), nullable=True),
    )
    op.create_foreign_key(
        "fk_hr_applications_employee_id",
        "hr_applications",
        "employees",
        ["employee_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_hr_applications_employee_id",
        "hr_applications",
        ["employee_id"],
        unique=False,
    )

    # -----------------------------
    # Onboarding plans (per employee)
    # -----------------------------
    op.create_table(
        "hr_onboarding_plans",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("store_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("application_id", sa.UUID(), nullable=True),
        # ACTIVE|COMPLETED|CANCELLED
        sa.Column("status", sa.String(length=16), nullable=False, server_default="ACTIVE"),
        sa.Column("start_date", sa.Date(), nullable=True),
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
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["application_id"], ["hr_applications.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hr_onboarding_plans_employee_id",
        "hr_onboarding_plans",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_onboarding_plans_store_id",
        "hr_onboarding_plans",
        ["store_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_onboarding_plans_status",
        "hr_onboarding_plans",
        ["status"],
        unique=False,
    )

    # -----------------------------
    # Onboarding tasks (checklist)
    # -----------------------------
    op.create_table(
        "hr_onboarding_tasks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        # TASK|DOCUMENT|ACTION
        sa.Column("task_type", sa.String(length=16), nullable=False, server_default="TASK"),
        # PENDING|DONE|BLOCKED
        sa.Column("status", sa.String(length=16), nullable=False, server_default="PENDING"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.ForeignKeyConstraint(["plan_id"], ["hr_onboarding_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hr_onboarding_tasks_plan_sort",
        "hr_onboarding_tasks",
        ["plan_id", "sort_order"],
        unique=False,
    )
    op.create_index(
        "ix_hr_onboarding_tasks_plan_status",
        "hr_onboarding_tasks",
        ["plan_id", "status"],
        unique=False,
    )

    # -----------------------------
    # Onboarding documents (local files tracked in DB)
    # -----------------------------
    op.create_table(
        "hr_employee_documents",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("plan_id", sa.UUID(), nullable=False),
        sa.Column("employee_id", sa.UUID(), nullable=False),
        sa.Column("doc_type", sa.String(length=32), nullable=False),
        sa.Column("original_filename", sa.Text(), nullable=False),
        # Relative path (under settings.data_dir)
        sa.Column("file_path", sa.Text(), nullable=False),
        # UPLOADED|VERIFIED|REJECTED
        sa.Column("status", sa.String(length=16), nullable=False, server_default="UPLOADED"),
        sa.Column("verified_by", sa.UUID(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(["plan_id"], ["hr_onboarding_plans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["employee_id"], ["employees.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_hr_employee_documents_employee_id",
        "hr_employee_documents",
        ["employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_employee_documents_plan_id",
        "hr_employee_documents",
        ["plan_id"],
        unique=False,
    )
    op.create_index(
        "ix_hr_employee_documents_doc_type",
        "hr_employee_documents",
        ["doc_type"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_hr_employee_documents_doc_type",
        table_name="hr_employee_documents",
    )
    op.drop_index(
        "ix_hr_employee_documents_plan_id",
        table_name="hr_employee_documents",
    )
    op.drop_index(
        "ix_hr_employee_documents_employee_id",
        table_name="hr_employee_documents",
    )
    op.drop_table("hr_employee_documents")

    op.drop_index("ix_hr_onboarding_tasks_plan_status", table_name="hr_onboarding_tasks")
    op.drop_index("ix_hr_onboarding_tasks_plan_sort", table_name="hr_onboarding_tasks")
    op.drop_table("hr_onboarding_tasks")

    op.drop_index("ix_hr_onboarding_plans_status", table_name="hr_onboarding_plans")
    op.drop_index("ix_hr_onboarding_plans_store_id", table_name="hr_onboarding_plans")
    op.drop_index("ix_hr_onboarding_plans_employee_id", table_name="hr_onboarding_plans")
    op.drop_table("hr_onboarding_plans")

    op.drop_index("ix_hr_applications_employee_id", table_name="hr_applications")
    op.drop_constraint(
        "fk_hr_applications_employee_id",
        "hr_applications",
        type_="foreignkey",
    )
    op.drop_column("hr_applications", "start_date")
    op.drop_column("hr_applications", "hired_at")
    op.drop_column("hr_applications", "employee_id")

