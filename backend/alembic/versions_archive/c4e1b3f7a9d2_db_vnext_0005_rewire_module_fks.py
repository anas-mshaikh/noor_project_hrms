"""DB vNext (0005): rewire module foreign keys to vNext masters.

Revision ID: c4e1b3f7a9d2
Revises: b3f7a9d2c4e1
Create Date: 2026-01-30

Goal:
- Make vNext schemas the ONLY canonical source of truth for:
  tenancy / iam / hr_core / workflow / dms
- Rewire all other module schemas to reference vNext masters via FKs.

Canonical mapping rules:
- org_id   -> tenant_id  (FK -> tenancy.tenants.id)
- store_id -> branch_id  (FK -> tenancy.branches.id)
- employee_id stays employee_id, but FK -> hr_core.employees.id

Hard-cutover assumption:
- No production data exists; we TRUNCATE affected module tables to safely apply
  NOT NULL columns and new FK constraints.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "c4e1b3f7a9d2"
down_revision = "b3f7a9d2c4e1"
branch_labels = None
depends_on = None


_VNEXT_ASSERT_TABLES: tuple[str, ...] = (
    "tenancy.tenants",
    "tenancy.companies",
    "tenancy.branches",
    "iam.users",
    "hr_core.employees",
)


def _table_exists(conn, schema: str, table: str) -> bool:
    return (
        conn.execute(
            sa.text("SELECT to_regclass(:fqtn)"),
            {"fqtn": f"{schema}.{table}"},
        ).scalar()
        is not None
    )


def _column_exists(conn, schema: str, table: str, column: str) -> bool:
    row = conn.execute(
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
    return row is not None


def _assert_vnext_present(conn) -> None:
    missing: list[str] = []
    for fqtn in _VNEXT_ASSERT_TABLES:
        exists = conn.execute(sa.text("SELECT to_regclass(:fqtn)"), {"fqtn": fqtn}).scalar()
        if exists is None:
            missing.append(fqtn)
    if missing:
        raise RuntimeError(
            "Refusing to rewire module FKs because vNext tables are missing: "
            + ", ".join(missing)
        )


def _print_column_inventory(conn) -> None:
    rows = conn.execute(
        sa.text(
            """
            SELECT table_schema, table_name, column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
              AND column_name IN ('org_id','store_id','employee_id','tenant_id','company_id','branch_id')
            ORDER BY table_schema, table_name, column_name
            """
        )
    ).fetchall()
    print(f"[db_vnext_0005] column inventory rows={len(rows)}")


def _truncate_if_exists(schema: str, table: str) -> None:
    conn = op.get_bind()
    if not _table_exists(conn, schema, table):
        return
    op.execute(f"TRUNCATE TABLE {schema}.{table} CASCADE")


def _rename_column_if_exists(schema: str, table: str, old: str, new: str) -> None:
    conn = op.get_bind()
    if not _table_exists(conn, schema, table):
        return
    if _column_exists(conn, schema, table, old) and not _column_exists(
        conn, schema, table, new
    ):
        op.alter_column(table, old, new_column_name=new, schema=schema)


def _add_column_if_missing(schema: str, table: str, column: sa.Column) -> None:
    conn = op.get_bind()
    if not _table_exists(conn, schema, table):
        return
    if not _column_exists(conn, schema, table, column.name):
        op.add_column(table, column, schema=schema)


def _create_fk(
    *,
    schema: str,
    table: str,
    column: str,
    ref_schema: str,
    ref_table: str,
    ref_column: str = "id",
    ondelete: str | None = None,
) -> None:
    name = f"fk_{schema}_{table}_{column}__{ref_schema}_{ref_table}"
    op.create_foreign_key(
        name,
        table,
        ref_table,
        [column],
        [ref_column],
        source_schema=schema,
        referent_schema=ref_schema,
        ondelete=ondelete,
    )


def _index_exists(conn, schema: str, index_name: str) -> bool:
    row = conn.execute(
        sa.text(
            """
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = :schema
              AND indexname = :index_name
            """
        ),
        {"schema": schema, "index_name": index_name},
    ).first()
    return row is not None


def _create_idx(schema: str, table: str, cols: list[str]) -> None:
    conn = op.get_bind()
    name = f"ix_{schema}_{table}_" + "_".join(cols)
    if _index_exists(conn, schema, name):
        return
    op.create_index(name, table, cols, unique=False, schema=schema)


def upgrade() -> None:
    conn = op.get_bind()
    _assert_vnext_present(conn)
    _print_column_inventory(conn)

    # ------------------------------------------------------------------
    # Hard cutover: clear module data so we can safely add new NOT NULL cols
    # and FK constraints without attempting to map legacy IDs.
    # ------------------------------------------------------------------
    # attendance
    for t in ("attendance_daily", "attendance_summary"):
        _truncate_if_exists("attendance", t)
    # vision
    for t in ("events", "tracks", "metrics_hourly", "artifacts", "jobs", "videos", "cameras"):
        _truncate_if_exists("vision", t)
    # face/mobile/imports/analytics/hr/work/skills
    _truncate_if_exists("face", "employee_faces")
    _truncate_if_exists("mobile", "mobile_accounts")
    for t in ("pos_summary",):
        _truncate_if_exists("analytics", t)
    for t in ("datasets", "month_state"):
        _truncate_if_exists("imports", t)
    for t in (
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
        "hr_onboarding_tasks",
        "hr_onboarding_plans",
    ):
        _truncate_if_exists("hr", t)
    for t in ("task_assignments", "task_required_skills", "tasks"):
        _truncate_if_exists("work", t)
    for t in ("employee_skills", "skill_taxonomy"):
        _truncate_if_exists("skills", t)

    # ------------------------------------------------------------------
    # Column renames: org_id -> tenant_id, store_id -> branch_id
    # ------------------------------------------------------------------
    # mobile.mobile_accounts is the only table with org_id today.
    _rename_column_if_exists("mobile", "mobile_accounts", "org_id", "tenant_id")

    # Branch-scoped tables (store_id -> branch_id).
    for schema, table in (
        ("vision", "cameras"),
        ("vision", "videos"),
        ("attendance", "attendance_daily"),
        ("imports", "datasets"),
        ("mobile", "mobile_accounts"),
        ("hr", "hr_openings"),
        ("hr", "hr_resume_batches"),
        ("hr", "hr_resumes"),
        ("hr", "hr_screening_runs"),
        ("hr", "hr_applications"),
        ("hr", "hr_onboarding_plans"),
        ("work", "tasks"),
    ):
        _rename_column_if_exists(schema, table, "store_id", "branch_id")

    # ------------------------------------------------------------------
    # Add tenant/company scope where required (hard cutover => NOT NULL).
    #
    # HR module (ATS + onboarding) must be tenant/company/branch scoped.
    # ------------------------------------------------------------------
    for table in (
        "hr_openings",
        "hr_resume_batches",
        "hr_resumes",
        "hr_screening_runs",
        "hr_applications",
        "hr_onboarding_plans",
    ):
        _add_column_if_missing(
            "hr",
            table,
            sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        )
        _add_column_if_missing(
            "hr",
            table,
            sa.Column("company_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        )

    # Add tenant scope to branch-scoped operational tables (common list/filter key).
    for schema, table in (
        ("vision", "cameras"),
        ("vision", "videos"),
        ("attendance", "attendance_daily"),
        ("imports", "datasets"),
        ("work", "tasks"),
    ):
        _add_column_if_missing(
            schema,
            table,
            sa.Column("tenant_id", sa.dialects.postgresql.UUID(as_uuid=True), nullable=False),
        )

    # ------------------------------------------------------------------
    # Foreign keys + indexes to vNext masters.
    #
    # Notes:
    # - FK names follow: fk_<schema>_<table>_<col>__<ref_schema>_<ref_table>
    # - We keep module-local FKs (e.g. vision.video_id -> vision.videos.id) as-is.
    # ------------------------------------------------------------------
    # tenant_id FKs
    for schema, table in (
        ("vision", "cameras"),
        ("vision", "videos"),
        ("attendance", "attendance_daily"),
        ("imports", "datasets"),
        ("work", "tasks"),
        ("hr", "hr_openings"),
        ("hr", "hr_resume_batches"),
        ("hr", "hr_resumes"),
        ("hr", "hr_screening_runs"),
        ("hr", "hr_applications"),
        ("hr", "hr_onboarding_plans"),
        ("mobile", "mobile_accounts"),
    ):
        if _column_exists(conn, schema, table, "tenant_id"):
            _create_fk(
                schema=schema,
                table=table,
                column="tenant_id",
                ref_schema="tenancy",
                ref_table="tenants",
                ondelete="CASCADE",
            )
            # mobile.mobile_accounts historically had an index on org_id; after
            # renaming org_id -> tenant_id, that index remains valid.
            if (schema, table) == ("mobile", "mobile_accounts") and _index_exists(
                conn, "mobile", "ix_mobile_accounts_org_id"
            ):
                continue
            _create_idx(schema, table, ["tenant_id"])

    # company_id FKs (HR module)
    for table in (
        "hr_openings",
        "hr_resume_batches",
        "hr_resumes",
        "hr_screening_runs",
        "hr_applications",
        "hr_onboarding_plans",
    ):
        if not _column_exists(conn, "hr", table, "company_id"):
            continue
        _create_fk(
            schema="hr",
            table=table,
            column="company_id",
            ref_schema="tenancy",
            ref_table="companies",
            ondelete="CASCADE",
        )
        _create_idx("hr", table, ["company_id"])

    # branch_id FKs (store -> branch cutover)
    for schema, table in (
        ("vision", "cameras"),
        ("vision", "videos"),
        ("attendance", "attendance_daily"),
        ("imports", "datasets"),
        ("mobile", "mobile_accounts"),
        ("hr", "hr_openings"),
        ("hr", "hr_resume_batches"),
        ("hr", "hr_resumes"),
        ("hr", "hr_screening_runs"),
        ("hr", "hr_applications"),
        ("hr", "hr_onboarding_plans"),
        ("work", "tasks"),
    ):
        if _column_exists(conn, schema, table, "branch_id"):
            _create_fk(
                schema=schema,
                table=table,
                column="branch_id",
                ref_schema="tenancy",
                ref_table="branches",
                ondelete="CASCADE",
            )
            # Most legacy tables already have an index on store_id; after renaming
            # to branch_id, that index remains valid. Avoid redundant indexes.

    # employee_id FKs to hr_core.employees
    for schema, table, col, ondelete in (
        ("attendance", "attendance_daily", "employee_id", "RESTRICT"),
        ("attendance", "attendance_summary", "employee_id", "RESTRICT"),
        ("vision", "events", "employee_id", "SET NULL"),
        ("vision", "tracks", "employee_id", "SET NULL"),
        ("face", "employee_faces", "employee_id", "CASCADE"),
        ("mobile", "mobile_accounts", "employee_id", "CASCADE"),
        ("analytics", "pos_summary", "employee_id", "RESTRICT"),
        ("hr", "hr_applications", "employee_id", "SET NULL"),
        ("hr", "hr_onboarding_plans", "employee_id", "CASCADE"),
        ("skills", "employee_skills", "employee_id", "CASCADE"),
        ("work", "task_assignments", "employee_id", "CASCADE"),
    ):
        if _column_exists(conn, schema, table, col):
            _create_fk(
                schema=schema,
                table=table,
                column=col,
                ref_schema="hr_core",
                ref_table="employees",
                ondelete=ondelete,
            )
            # Avoid redundant indexes where legacy schemas already have them.
            # We still add missing ones for derived/PK-leading-column cases.
            if (schema, table) in {
                ("attendance", "attendance_summary"),
                ("analytics", "pos_summary"),
            }:
                _create_idx(schema, table, [col])


def downgrade() -> None:
    # Treat this as a permanent cutover; we intentionally do not attempt to
    # recreate legacy FKs/columns.
    pass
