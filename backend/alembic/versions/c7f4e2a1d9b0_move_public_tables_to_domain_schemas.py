"""Move tables from public schema into domain schemas.

Revision ID: c7f4e2a1d9b0
Revises: 7b2c1d0e9a31
Create Date: 2026-01-26

This is a "big bang" migration that moves existing tables from the `public` schema
into domain-specific schemas:

- core: organizations, stores, employees
- vision: cameras, videos, jobs, tracks, events, metrics_hourly, artifacts
- attendance: attendance_daily, attendance_summary
- hr: all hr_* tables
- mobile: mobile_accounts
- face: employee_faces
- imports: datasets, month_state
- analytics: pos_summary

We intentionally leave `public.alembic_version` in `public`.
Extensions (e.g. pgvector) also remain in their existing schema.
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision = "c7f4e2a1d9b0"
down_revision = "7b2c1d0e9a31"
branch_labels = None
depends_on = None


def _create_schema(schema: str) -> None:
    op.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")


def _move_table(table: str, schema: str) -> None:
    # Use IF EXISTS so this migration is tolerant to partially applied dev DBs.
    op.execute(f"ALTER TABLE IF EXISTS public.{table} SET SCHEMA {schema}")


def _move_owned_sequences(table: str, schema: str) -> None:
    """
    Move sequences that are OWNED BY columns of the given table into the same schema.

    Most of our tables use UUID primary keys (no sequences), but this keeps the
    migration correct if any SERIAL/IDENTITY columns exist now or in the future.
    """

    # NOTE: Be careful with naming here: plpgsql variables and SQL aliases share
    # a namespace. We avoid naming collisions by using distinct suffixes.
    op.execute(
        f"""
DO $$
DECLARE seq_rec record;
BEGIN
  FOR seq_rec IN
    SELECT seq_ns.nspname AS seq_schema, seq_cls.relname AS seq_name
    FROM pg_class seq_cls
    JOIN pg_namespace seq_ns ON seq_ns.oid = seq_cls.relnamespace
    JOIN pg_depend dep ON dep.objid = seq_cls.oid
    JOIN pg_class tbl_cls ON dep.refobjid = tbl_cls.oid
    JOIN pg_namespace tbl_ns ON tbl_ns.oid = tbl_cls.relnamespace
    WHERE seq_cls.relkind = 'S'
      AND dep.deptype = 'a'
      AND tbl_ns.nspname = '{schema}'
      AND tbl_cls.relname = '{table}'
  LOOP
    IF seq_rec.seq_schema <> '{schema}' THEN
      EXECUTE format(
        'ALTER SEQUENCE %I.%I SET SCHEMA %I',
        seq_rec.seq_schema,
        seq_rec.seq_name,
        '{schema}'
      );
    END IF;
  END LOOP;
END $$;
"""
    )


def upgrade() -> None:
    # ---------------------------------------------------------------------
    # 1) Create schemas (idempotent).
    # ---------------------------------------------------------------------
    for schema in (
        "core",
        "vision",
        "attendance",
        "hr",
        "mobile",
        "face",
        "imports",
        "analytics",
    ):
        _create_schema(schema)

    # ---------------------------------------------------------------------
    # 2) Move tables from public -> domain schema.
    #
    # Postgres keeps constraints, indexes, and FKs intact when moving tables.
    # ---------------------------------------------------------------------
    # Root/core tables first.
    for table in ("organizations", "stores", "employees"):
        _move_table(table, "core")

    # Vision (CCTV processing) tables.
    for table in (
        "cameras",
        "videos",
        "jobs",
        "tracks",
        "events",
        "metrics_hourly",
        "artifacts",
    ):
        _move_table(table, "vision")

    # Attendance tables.
    for table in ("attendance_daily", "attendance_summary"):
        _move_table(table, "attendance")

    # HR tables (all prefixed hr_*).
    for table in (
        "hr_openings",
        "hr_resume_batches",
        "hr_resumes",
        "hr_resume_views",
        "hr_screening_runs",
        "hr_screening_results",
        "hr_screening_explanations",
        "hr_pipeline_stages",
        "hr_applications",
        "hr_application_notes",
        "hr_onboarding_plans",
        "hr_onboarding_tasks",
        "hr_employee_documents",
    ):
        _move_table(table, "hr")

    # Mobile + face + imports + analytics.
    _move_table("mobile_accounts", "mobile")
    _move_table("employee_faces", "face")

    for table in ("datasets", "month_state"):
        _move_table(table, "imports")

    _move_table("pos_summary", "analytics")

    # ---------------------------------------------------------------------
    # 3) Move owned sequences (if any) to match table schema.
    # ---------------------------------------------------------------------
    # core
    for table in ("organizations", "stores", "employees"):
        _move_owned_sequences(table, "core")

    # vision
    for table in (
        "cameras",
        "videos",
        "jobs",
        "tracks",
        "events",
        "metrics_hourly",
        "artifacts",
    ):
        _move_owned_sequences(table, "vision")

    # attendance
    for table in ("attendance_daily", "attendance_summary"):
        _move_owned_sequences(table, "attendance")

    # hr
    for table in (
        "hr_openings",
        "hr_resume_batches",
        "hr_resumes",
        "hr_resume_views",
        "hr_screening_runs",
        "hr_screening_results",
        "hr_screening_explanations",
        "hr_pipeline_stages",
        "hr_applications",
        "hr_application_notes",
        "hr_onboarding_plans",
        "hr_onboarding_tasks",
        "hr_employee_documents",
    ):
        _move_owned_sequences(table, "hr")

    # mobile / face / imports / analytics
    _move_owned_sequences("mobile_accounts", "mobile")
    _move_owned_sequences("employee_faces", "face")
    for table in ("datasets", "month_state"):
        _move_owned_sequences(table, "imports")
    _move_owned_sequences("pos_summary", "analytics")


def downgrade() -> None:
    # Move tables back into public (best-effort).
    #
    # NOTE: We intentionally do NOT drop schemas in downgrade to avoid destroying
    # any non-table objects that may have been created after upgrade.
    for table in ("pos_summary",):
        op.execute(f"ALTER TABLE IF EXISTS analytics.{table} SET SCHEMA public")
    for table in ("datasets", "month_state"):
        op.execute(f"ALTER TABLE IF EXISTS imports.{table} SET SCHEMA public")
    op.execute("ALTER TABLE IF EXISTS face.employee_faces SET SCHEMA public")
    op.execute("ALTER TABLE IF EXISTS mobile.mobile_accounts SET SCHEMA public")

    for table in (
        "hr_employee_documents",
        "hr_onboarding_tasks",
        "hr_onboarding_plans",
        "hr_application_notes",
        "hr_applications",
        "hr_pipeline_stages",
        "hr_screening_explanations",
        "hr_screening_results",
        "hr_screening_runs",
        "hr_resume_views",
        "hr_resumes",
        "hr_resume_batches",
        "hr_openings",
    ):
        op.execute(f"ALTER TABLE IF EXISTS hr.{table} SET SCHEMA public")

    for table in ("attendance_daily", "attendance_summary"):
        op.execute(f"ALTER TABLE IF EXISTS attendance.{table} SET SCHEMA public")

    for table in (
        "artifacts",
        "metrics_hourly",
        "events",
        "tracks",
        "jobs",
        "videos",
        "cameras",
    ):
        op.execute(f"ALTER TABLE IF EXISTS vision.{table} SET SCHEMA public")

    for table in ("employees", "stores", "organizations"):
        op.execute(f"ALTER TABLE IF EXISTS core.{table} SET SCHEMA public")

    # Best-effort: move any owned sequences back to public as well.
    for table in (
        "organizations",
        "stores",
        "employees",
        "cameras",
        "videos",
        "jobs",
        "tracks",
        "events",
        "metrics_hourly",
        "artifacts",
        "attendance_daily",
        "attendance_summary",
        "hr_openings",
        "hr_resume_batches",
        "hr_resumes",
        "hr_resume_views",
        "hr_screening_runs",
        "hr_screening_results",
        "hr_screening_explanations",
        "hr_pipeline_stages",
        "hr_applications",
        "hr_application_notes",
        "hr_onboarding_plans",
        "hr_onboarding_tasks",
        "hr_employee_documents",
        "mobile_accounts",
        "employee_faces",
        "datasets",
        "month_state",
        "pos_summary",
    ):
        _move_owned_sequences(table, "public")
