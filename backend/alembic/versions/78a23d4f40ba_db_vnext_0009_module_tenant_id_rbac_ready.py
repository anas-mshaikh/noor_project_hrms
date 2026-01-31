"""DB vNext (0009): add tenant_id to module business tables (RLS-ready).

Revision ID: 78a23d4f40ba
Revises: 88e00e12d1a9
Create Date: 2026-01-30

Goal:
- Add `tenant_id` to key module/business tables that are frequently filtered by
  tenant (analytics summaries, face embeddings, HR module tables, vision pipeline).
- Do NOT add tenant_id to global lookup tables (roles/permissions/request_types),
  and allow some deep child tables to inherit tenancy via parent FKs.

Hard-cutover assumption:
- No production data exists. If we cannot infer tenant_id for existing rows, we
  raise with a clear instruction to reset the dev DB volume.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "78a23d4f40ba"
down_revision = "88e00e12d1a9"
branch_labels = None
depends_on = None


def _table_exists(conn, schema: str, table: str) -> bool:
    return (
        conn.execute(sa.text("SELECT to_regclass(:fqtn)"), {"fqtn": f"{schema}.{table}"}).scalar()
        is not None
    )


def _column_exists(conn, schema: str, table: str, column: str) -> bool:
    return (
        conn.execute(
            sa.text(
                """
                SELECT 1
                FROM information_schema.columns
                WHERE table_schema = :schema
                  AND table_name = :table
                  AND column_name = :column
                """
            ),
            {"schema": schema, "table": table, "column": column},
        ).first()
        is not None
    )


def _constraint_exists(conn, schema: str, constraint_name: str) -> bool:
    return (
        conn.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_constraint c
                JOIN pg_namespace n ON n.oid = c.connamespace
                WHERE n.nspname = :schema
                  AND c.conname = :name
                """
            ),
            {"schema": schema, "name": constraint_name},
        ).first()
        is not None
    )


def _index_exists(conn, schema: str, index_name: str) -> bool:
    return (
        conn.execute(
            sa.text(
                """
                SELECT 1
                FROM pg_indexes
                WHERE schemaname = :schema
                  AND indexname = :name
                """
            ),
            {"schema": schema, "name": index_name},
        ).first()
        is not None
    )


def _add_tenant_id_column(conn, schema: str, table: str) -> None:
    if not _table_exists(conn, schema, table):
        return
    if _column_exists(conn, schema, table, "tenant_id"):
        return
    op.add_column(
        table,
        sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=True),
        schema=schema,
    )


def _backfill_and_require_not_null(conn, schema: str, table: str, backfill_sql: str) -> None:
    if not _table_exists(conn, schema, table) or not _column_exists(conn, schema, table, "tenant_id"):
        return

    op.execute(backfill_sql)
    nulls = conn.execute(
        sa.text(f"SELECT count(*) FROM {schema}.{table} WHERE tenant_id IS NULL")
    ).scalar()
    if nulls and int(nulls) > 0:
        raise RuntimeError(
            f"{schema}.{table}: unable to backfill tenant_id for {nulls} rows. "
            "This is a hard-cutover dev DB; reset your volume (docker compose down -v)."
        )
    op.execute(f"ALTER TABLE {schema}.{table} ALTER COLUMN tenant_id SET NOT NULL")


def _ensure_tenant_fk_and_index(conn, schema: str, table: str) -> None:
    if not _table_exists(conn, schema, table) or not _column_exists(conn, schema, table, "tenant_id"):
        return

    fk_name = f"fk_{schema}_{table}_tenant_id__tenancy_tenants"
    if not _constraint_exists(conn, schema, fk_name):
        op.create_foreign_key(
            fk_name,
            table,
            "tenants",
            ["tenant_id"],
            ["id"],
            source_schema=schema,
            referent_schema="tenancy",
            ondelete="CASCADE",
        )

    ix_name = f"ix_{schema}_{table}_tenant_id"
    if not _index_exists(conn, schema, ix_name):
        op.create_index(ix_name, table, ["tenant_id"], unique=False, schema=schema)


def upgrade() -> None:
    conn = op.get_bind()

    # Safety: ensure vNext tenancy exists before we tenant-scope module tables.
    if not _table_exists(conn, "tenancy", "tenants"):
        raise RuntimeError("Missing tenancy.tenants; run DB vNext migrations first.")

    # ------------------------------------------------------------------
    # Analytics / summaries (directly queried by tenant)
    # ------------------------------------------------------------------
    for schema, table, backfill in (
        (
            "analytics",
            "pos_summary",
            """
            UPDATE analytics.pos_summary p
            SET tenant_id = d.tenant_id
            FROM imports.datasets d
            WHERE d.id = p.dataset_id
              AND p.tenant_id IS NULL
            """,
        ),
        (
            "attendance",
            "attendance_summary",
            """
            UPDATE attendance.attendance_summary a
            SET tenant_id = d.tenant_id
            FROM imports.datasets d
            WHERE d.id = a.dataset_id
              AND a.tenant_id IS NULL
            """,
        ),
    ):
        _add_tenant_id_column(conn, schema, table)
        _backfill_and_require_not_null(conn, schema, table, backfill)
        _ensure_tenant_fk_and_index(conn, schema, table)

    # ------------------------------------------------------------------
    # Face embeddings (employee scoped, frequently filtered by tenant)
    # ------------------------------------------------------------------
    if _table_exists(conn, "face", "employee_faces"):
        _add_tenant_id_column(conn, "face", "employee_faces")
        _backfill_and_require_not_null(
            conn,
            "face",
            "employee_faces",
            """
            UPDATE face.employee_faces f
            SET tenant_id = e.tenant_id
            FROM hr_core.employees e
            WHERE e.id = f.employee_id
              AND f.tenant_id IS NULL
            """,
        )
        _ensure_tenant_fk_and_index(conn, "face", "employee_faces")

    # ------------------------------------------------------------------
    # HR module (ATS / onboarding): tenant scope for list/filter + future RLS
    # ------------------------------------------------------------------
    hr_tables: tuple[tuple[str, str], ...] = (
        ("hr_pipeline_stages", "hr_openings"),
        ("hr_application_notes", "hr_applications"),
        ("hr_onboarding_tasks", "hr_onboarding_plans"),
        ("hr_resume_views", "hr_resumes"),
    )
    for child, parent in hr_tables:
        if not _table_exists(conn, "hr", child) or not _table_exists(conn, "hr", parent):
            continue
        _add_tenant_id_column(conn, "hr", child)
        _backfill_and_require_not_null(
            conn,
            "hr",
            child,
            f"""
            UPDATE hr.{child} c
            SET tenant_id = p.tenant_id
            FROM hr.{parent} p
            WHERE p.id = c.{ 'opening_id' if child == 'hr_pipeline_stages' else ('application_id' if child == 'hr_application_notes' else ('plan_id' if child == 'hr_onboarding_tasks' else 'resume_id')) }
              AND c.tenant_id IS NULL
            """,
        )
        _ensure_tenant_fk_and_index(conn, "hr", child)

    for table in ("hr_screening_results", "hr_screening_explanations"):
        if not _table_exists(conn, "hr", table) or not _table_exists(conn, "hr", "hr_screening_runs"):
            continue
        _add_tenant_id_column(conn, "hr", table)
        _backfill_and_require_not_null(
            conn,
            "hr",
            table,
            f"""
            UPDATE hr.{table} t
            SET tenant_id = r.tenant_id
            FROM hr.hr_screening_runs r
            WHERE r.id = t.run_id
              AND t.tenant_id IS NULL
            """,
        )
        _ensure_tenant_fk_and_index(conn, "hr", table)

    # ------------------------------------------------------------------
    # Skills: make taxonomy tenant-aware (common in enterprise HRMS)
    # ------------------------------------------------------------------
    if _table_exists(conn, "skills", "skill_taxonomy"):
        _add_tenant_id_column(conn, "skills", "skill_taxonomy")

        # If there are existing rows, we can only safely assign them if there is
        # exactly one tenant (dev default).
        taxonomy_rows = conn.execute(sa.text("SELECT count(*) FROM skills.skill_taxonomy")).scalar() or 0
        if int(taxonomy_rows) > 0:
            tenant_ids = [r[0] for r in conn.execute(sa.text("SELECT id FROM tenancy.tenants ORDER BY created_at"))]
            if len(tenant_ids) != 1:
                raise RuntimeError(
                    "skills.skill_taxonomy has rows but cannot infer tenant_id (multiple tenants exist). "
                    "Reset dev DB or repopulate taxonomy per tenant."
                )
            conn.execute(
                sa.text(
                    "UPDATE skills.skill_taxonomy SET tenant_id = :tenant_id WHERE tenant_id IS NULL"
                ),
                {"tenant_id": tenant_ids[0]},
            )

        # Enforce tenant-aware uniqueness on code.
        op.execute("ALTER TABLE skills.skill_taxonomy DROP CONSTRAINT IF EXISTS uq_skill_taxonomy_code")
        op.execute(
            "ALTER TABLE skills.skill_taxonomy "
            "ADD CONSTRAINT uq_skill_taxonomy_tenant_code UNIQUE (tenant_id, code)"
        )

        nulls = conn.execute(
            sa.text("SELECT count(*) FROM skills.skill_taxonomy WHERE tenant_id IS NULL")
        ).scalar()
        if nulls and int(nulls) > 0:
            raise RuntimeError(
                f"skills.skill_taxonomy has {nulls} rows with tenant_id NULL; cannot enforce tenancy."
            )
        op.execute("ALTER TABLE skills.skill_taxonomy ALTER COLUMN tenant_id SET NOT NULL")
        _ensure_tenant_fk_and_index(conn, "skills", "skill_taxonomy")

    if _table_exists(conn, "skills", "employee_skills"):
        _add_tenant_id_column(conn, "skills", "employee_skills")
        _backfill_and_require_not_null(
            conn,
            "skills",
            "employee_skills",
            """
            UPDATE skills.employee_skills s
            SET tenant_id = e.tenant_id
            FROM hr_core.employees e
            WHERE e.id = s.employee_id
              AND s.tenant_id IS NULL
            """,
        )
        _ensure_tenant_fk_and_index(conn, "skills", "employee_skills")

    # ------------------------------------------------------------------
    # Work: assignments should be tenant scoped (for queues/reporting)
    # ------------------------------------------------------------------
    for table in ("task_assignments", "task_required_skills"):
        if not _table_exists(conn, "work", table) or not _table_exists(conn, "work", "tasks"):
            continue
        _add_tenant_id_column(conn, "work", table)
        _backfill_and_require_not_null(
            conn,
            "work",
            table,
            f"""
            UPDATE work.{table} x
            SET tenant_id = t.tenant_id
            FROM work.tasks t
            WHERE t.id = x.task_id
              AND x.tenant_id IS NULL
            """,
        )
        _ensure_tenant_fk_and_index(conn, "work", table)

    # ------------------------------------------------------------------
    # Vision pipeline derived tables: add tenant_id for simpler filtering.
    # ------------------------------------------------------------------
    if _table_exists(conn, "vision", "jobs") and _table_exists(conn, "vision", "videos"):
        _add_tenant_id_column(conn, "vision", "jobs")
        _backfill_and_require_not_null(
            conn,
            "vision",
            "jobs",
            """
            UPDATE vision.jobs j
            SET tenant_id = v.tenant_id
            FROM vision.videos v
            WHERE v.id = j.video_id
              AND j.tenant_id IS NULL
            """,
        )
        _ensure_tenant_fk_and_index(conn, "vision", "jobs")

    for table in ("events", "tracks", "artifacts", "metrics_hourly"):
        if not _table_exists(conn, "vision", table) or not _table_exists(conn, "vision", "jobs"):
            continue
        _add_tenant_id_column(conn, "vision", table)
        _backfill_and_require_not_null(
            conn,
            "vision",
            table,
            f"""
            UPDATE vision.{table} x
            SET tenant_id = j.tenant_id
            FROM vision.jobs j
            WHERE j.id = x.job_id
              AND x.tenant_id IS NULL
            """,
        )
        _ensure_tenant_fk_and_index(conn, "vision", table)

    # ------------------------------------------------------------------
    # Imports: month_state is a global pointer today, but tenant_id is useful for
    # filtering/admin. We add the column (nullable) without changing its PK here.
    # ------------------------------------------------------------------
    if _table_exists(conn, "imports", "month_state"):
        _add_tenant_id_column(conn, "imports", "month_state")
        # Backfill when published_dataset_id is present.
        op.execute(
            """
            UPDATE imports.month_state m
            SET tenant_id = d.tenant_id
            FROM imports.datasets d
            WHERE d.id = m.published_dataset_id
              AND m.tenant_id IS NULL
            """
        )
        _ensure_tenant_fk_and_index(conn, "imports", "month_state")


def downgrade() -> None:
    raise NotImplementedError("DB vNext migrations are forward-only after hard cutover.")

