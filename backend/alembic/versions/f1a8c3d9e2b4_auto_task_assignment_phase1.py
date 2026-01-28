"""Auto task assignment (Phase 1): skills + work schemas.

Revision ID: f1a8c3d9e2b4
Revises: c7f4e2a1d9b0
Create Date: 2026-01-27

This migration introduces two new domain schemas and the minimal tables required
for a deterministic, auditable "auto task assignment" system:

- skills: skill taxonomy + employee skill proficiency
- work: tasks + required skills + assignment decision log

Important design notes:
- We keep these tables OUT of `public` and OUT of `hr` to avoid future coupling.
- Foreign keys are schema-qualified (core / skills / work).
- `work.task_assignments` is append-only by design (reassignment creates a new row).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID


# revision identifiers, used by Alembic.
revision = "f1a8c3d9e2b4"
down_revision = "c7f4e2a1d9b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create schemas (idempotent).
    op.execute("CREATE SCHEMA IF NOT EXISTS skills")
    op.execute("CREATE SCHEMA IF NOT EXISTS work")

    op.create_table(
        "skill_taxonomy",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("code", name="uq_skill_taxonomy_code"),
        schema="skills",
    )

    op.create_table(
        "employee_skills",
        sa.Column("employee_id", UUID(as_uuid=True), nullable=False),
        sa.Column("skill_id", UUID(as_uuid=True), nullable=False),
        sa.Column("proficiency", sa.Integer(), nullable=False),
        sa.Column(
            "confidence",
            sa.Float(),
            nullable=False,
            server_default=sa.text("1.0"),
        ),
        sa.Column("source", sa.String(length=32), nullable=True),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["core.employees.id"],
            name="fk_employee_skills_employee_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skills.skill_taxonomy.id"],
            name="fk_employee_skills_skill_id",
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            "proficiency >= 1 AND proficiency <= 5",
            name="ck_employee_skills_proficiency_1_5",
        ),
        sa.PrimaryKeyConstraint("employee_id", "skill_id", name="pk_employee_skills"),
        schema="skills",
    )
    op.create_index(
        "ix_employee_skills_employee_id",
        "employee_skills",
        ["employee_id"],
        unique=False,
        schema="skills",
    )
    op.create_index(
        "ix_employee_skills_skill_id",
        "employee_skills",
        ["skill_id"],
        unique=False,
        schema="skills",
    )

    op.create_table(
        "tasks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("store_id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=True),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("3"),
        ),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["core.stores.id"],
            name="fk_work_tasks_store_id",
            ondelete="CASCADE",
        ),
        schema="work",
    )
    op.create_index(
        "ix_work_tasks_store_status",
        "tasks",
        ["store_id", "status"],
        unique=False,
        schema="work",
    )

    op.create_table(
        "task_required_skills",
        sa.Column("task_id", UUID(as_uuid=True), nullable=False),
        sa.Column("skill_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "min_proficiency",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "required",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["work.tasks.id"],
            name="fk_task_required_skills_task_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["skills.skill_taxonomy.id"],
            name="fk_task_required_skills_skill_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "task_id", "skill_id", name="pk_task_required_skills"
        ),
        schema="work",
    )

    op.create_table(
        "task_assignments",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("task_id", UUID(as_uuid=True), nullable=False),
        sa.Column("employee_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "assigned_by",
            sa.String(length=32),
            nullable=False,
            server_default=sa.text("'auto'"),
        ),
        # Deterministic score used for audit/debug; always present (even for manual overrides).
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column(
            "assigned_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["task_id"],
            ["work.tasks.id"],
            name="fk_task_assignments_task_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["employee_id"],
            ["core.employees.id"],
            name="fk_task_assignments_employee_id",
            ondelete="CASCADE",
        ),
        schema="work",
    )
    op.create_index(
        "ix_task_assignments_task_id",
        "task_assignments",
        ["task_id"],
        unique=False,
        schema="work",
    )
    op.create_index(
        "ix_task_assignments_employee_id",
        "task_assignments",
        ["employee_id"],
        unique=False,
        schema="work",
    )


def downgrade() -> None:
    op.drop_index(
        "ix_task_assignments_employee_id", table_name="task_assignments", schema="work"
    )
    op.drop_index(
        "ix_task_assignments_task_id", table_name="task_assignments", schema="work"
    )
    op.drop_table("task_assignments", schema="work")
    op.drop_table("task_required_skills", schema="work")
    op.drop_index(
        "ix_work_tasks_store_status", table_name="tasks", schema="work"
    )
    op.drop_table("tasks", schema="work")

    op.drop_index(
        "ix_employee_skills_skill_id", table_name="employee_skills", schema="skills"
    )
    op.drop_index(
        "ix_employee_skills_employee_id",
        table_name="employee_skills",
        schema="skills",
    )
    op.drop_table("employee_skills", schema="skills")
    op.drop_table("skill_taxonomy", schema="skills")

    # We intentionally do NOT drop schemas in downgrade to avoid deleting any
    # additional objects that might have been created after upgrade.
