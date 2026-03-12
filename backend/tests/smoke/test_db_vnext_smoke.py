"""
DB vNext smoke test.

DB vNext smoke test for the enterprise foundation schemas:
  tenancy, iam, hr_core, workflow, dms

This script runs INSERT checks inside a transaction and ROLLS BACK at the end,
so it is safe to run on every startup.

Usage (from repo root):
  python3 backend/tests/smoke/test_db_vnext_smoke.py

Optional:
  python3 backend/tests/smoke/test_db_vnext_smoke.py --database-url postgresql://...
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine.url import make_url


def _ensure_backend_on_path() -> None:
    # When this file lives at:
    #   backend/tests/smoke/test_db_vnext_smoke.py
    # we expect:
    #   parents[0] = smoke/
    #   parents[1] = tests/
    #   parents[2] = backend/
    backend_dir = Path(__file__).resolve().parents[2]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


def _require_uuid(conn, sql: str, params: dict, name: str):
    row = conn.execute(text(sql), params).fetchone()
    if not row or not row[0]:
        raise RuntimeError(f"Missing required row: {name}")
    return row[0]


def _table_exists(conn, schema: str, table: str) -> bool:
    return (
        conn.execute(
            text("SELECT to_regclass(:fqtn)"),
            {"fqtn": f"{schema}.{table}"},
        ).scalar()
        is not None
    )


def _column_exists(conn, schema: str, table: str, column: str) -> bool:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = :schema
              AND table_name = :table
              AND column_name = :column
            """
        ),
        {"schema": schema, "table": table, "column": column},
    ).fetchone()
    return row is not None


def _warn(msg: str) -> None:
    print(f"[db_vnext_smoke] WARN: {msg}")


def _assert_required_columns(conn, schema: str, table: str, columns: list[str]) -> None:
    missing = [column for column in columns if not _column_exists(conn, schema, table, column)]
    if missing:
        raise RuntimeError(f"Missing columns on {schema}.{table}: {', '.join(missing)}")


def _assert_index(conn, schema: str, index_name: str) -> None:
    row = conn.execute(
        text(
            """
            SELECT 1
            FROM pg_indexes
            WHERE schemaname = :schema
              AND indexname = :index_name
            """
        ),
        {"schema": schema, "index_name": index_name},
    ).fetchone()
    if not row:
        raise RuntimeError(f"Missing index: {schema}.{index_name}")


def _load_database_url_from_dotenv() -> str | None:
    # Keep this dependency-free (no python-dotenv).
    # Only parse simple KEY=VALUE lines for DATABASE_URL.
    backend_dir = Path(__file__).resolve().parents[2]
    repo_root = backend_dir.parent
    candidates = [
        repo_root / ".env.local",
        repo_root / ".env",
        backend_dir / ".env.local",
        backend_dir / ".env",
        backend_dir / ".env.docker",
    ]

    for path in candidates:
        if not path.exists():
            continue
        try:
            for raw in path.read_text(encoding="utf-8").splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                key, value = line.split("=", 1)
                if key.strip() != "DATABASE_URL":
                    continue
                v = value.strip().strip("'").strip('"')
                return v or None
        except Exception:
            continue
    return None


def _normalize_database_url_for_local(db_url: str) -> str:
    # In docker-compose the app connects to Postgres via host "db", but when this
    # script runs on the host, "db" won't resolve. Rewrite to localhost unless
    # we are running inside Docker.
    if Path("/.dockerenv").exists():
        return db_url
    try:
        url = make_url(db_url)
        if url.host == "db":
            url = url.set(host="localhost")
            return url.render_as_string(hide_password=False)
    except Exception:
        pass
    return db_url


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL (defaults to env DATABASE_URL / .env files).",
    )
    args = parser.parse_args()

    _ensure_backend_on_path()

    db_url = (
        args.database_url
        or os.getenv("DATABASE_URL")
        or _load_database_url_from_dotenv()
        # Fallback for common local docker-compose defaults.
        or "postgresql+psycopg://attendance:attendance@localhost:5432/attendance"
    )
    db_url = _normalize_database_url_for_local(db_url)
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant_id = uuid4()
    company_id = uuid4()
    branch_id = uuid4()

    requester_user_id = uuid4()
    approver_user_id = uuid4()

    person_id = uuid4()
    employee_id = uuid4()

    workflow_def_id = uuid4()
    request_id = uuid4()
    request_step_id = uuid4()

    file_id = uuid4()
    attachment_id = uuid4()

    today = date.today()
    employee_code = f"E-{employee_id.hex[:8].upper()}"

    requester_email = f"requester+{requester_user_id.hex[:10]}@example.com"
    approver_email = f"approver+{approver_user_id.hex[:10]}@example.com"

    with engine.connect() as conn:
        tx = conn.begin()
        try:
            # ------------------------------------------------------------------
            # tenancy
            # ------------------------------------------------------------------
            conn.execute(
                text(
                    """
                    INSERT INTO tenancy.tenants (id, name, status)
                    VALUES (:id, :name, 'ACTIVE')
                    """
                ),
                {"id": tenant_id, "name": f"Smoke Tenant {tenant_id.hex[:6]}"},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO tenancy.companies (id, tenant_id, name, legal_name, currency_code, timezone, status)
                    VALUES (:id, :tenant_id, :name, :legal_name, 'SAR', 'Asia/Riyadh', 'ACTIVE')
                    """
                ),
                {
                    "id": company_id,
                    "tenant_id": tenant_id,
                    "name": f"Smoke Company {company_id.hex[:6]}",
                    "legal_name": f"Smoke Company {company_id.hex[:6]} LLC",
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO tenancy.branches (id, tenant_id, company_id, name, code, timezone, address, status)
                    VALUES (:id, :tenant_id, :company_id, :name, :code, 'Asia/Riyadh', '{}'::jsonb, 'ACTIVE')
                    """
                ),
                {
                    "id": branch_id,
                    "tenant_id": tenant_id,
                    "company_id": company_id,
                    "name": "HQ Branch",
                    "code": f"HQ{branch_id.hex[:3].upper()}",
                },
            )

            # ------------------------------------------------------------------
            # iam
            # ------------------------------------------------------------------
            conn.execute(
                text(
                    """
                    INSERT INTO iam.users (id, email, phone, password_hash, status)
                    VALUES (:id, :email, NULL, NULL, 'ACTIVE')
                    """
                ),
                {"id": requester_user_id, "email": requester_email},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO iam.users (id, email, phone, password_hash, status)
                    VALUES (:id, :email, NULL, NULL, 'ACTIVE')
                    """
                ),
                {"id": approver_user_id, "email": approver_email},
            )

            role_employee_id = _require_uuid(
                conn,
                "SELECT id FROM iam.roles WHERE code = :code",
                {"code": "EMPLOYEE"},
                "iam.roles(EMPLOYEE)",
            )
            role_hr_manager_id = _require_uuid(
                conn,
                "SELECT id FROM iam.roles WHERE code = :code",
                {"code": "HR_MANAGER"},
                "iam.roles(HR_MANAGER)",
            )

            conn.execute(
                text(
                    """
                    INSERT INTO iam.user_roles (user_id, tenant_id, company_id, branch_id, role_id)
                    VALUES (:user_id, :tenant_id, :company_id, :branch_id, :role_id)
                    """
                ),
                {
                    "user_id": requester_user_id,
                    "tenant_id": tenant_id,
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "role_id": role_employee_id,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO iam.user_roles (user_id, tenant_id, company_id, branch_id, role_id)
                    VALUES (:user_id, :tenant_id, :company_id, :branch_id, :role_id)
                    """
                ),
                {
                    "user_id": approver_user_id,
                    "tenant_id": tenant_id,
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "role_id": role_hr_manager_id,
                },
            )

            # ------------------------------------------------------------------
            # hr_core
            # ------------------------------------------------------------------
            conn.execute(
                text(
                    """
                    INSERT INTO hr_core.persons (id, tenant_id, first_name, last_name, dob, nationality, email, phone, address)
                    VALUES (:id, :tenant_id, 'Smoke', 'Employee', NULL, NULL, :email, NULL, '{}'::jsonb)
                    """
                ),
                {"id": person_id, "tenant_id": tenant_id, "email": requester_email},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO hr_core.employees (id, tenant_id, company_id, person_id, employee_code, status, join_date)
                    VALUES (:id, :tenant_id, :company_id, :person_id, :employee_code, 'ACTIVE', :join_date)
                    """
                ),
                {
                    "id": employee_id,
                    "tenant_id": tenant_id,
                    "company_id": company_id,
                    "person_id": person_id,
                    "employee_code": employee_code,
                    "join_date": today,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO hr_core.employee_employment (
                      tenant_id, company_id, employee_id, branch_id, org_unit_id, job_title_id, grade_id,
                      manager_employee_id, start_date, end_date, is_primary
                    ) VALUES (
                      :tenant_id, :company_id, :employee_id, :branch_id, NULL, NULL, NULL,
                      NULL, :start_date, NULL, true
                    )
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "company_id": company_id,
                    "employee_id": employee_id,
                    "branch_id": branch_id,
                    "start_date": today,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO hr_core.employee_user_links (employee_id, user_id)
                    VALUES (:employee_id, :user_id)
                    """
                ),
                {"employee_id": employee_id, "user_id": requester_user_id},
            )

            # ------------------------------------------------------------------
            # workflow
            # ------------------------------------------------------------------
            request_type_id = _require_uuid(
                conn,
                "SELECT id FROM workflow.request_types WHERE code = :code",
                {"code": "GENERAL_REQUEST"},
                "workflow.request_types(GENERAL_REQUEST)",
            )

            conn.execute(
                text(
                    """
                    INSERT INTO workflow.workflow_definitions (
                      id, tenant_id, company_id, request_type_id, name, is_active, created_by
                    ) VALUES (
                      :id, :tenant_id, :company_id, :request_type_id, :name, true, :created_by
                    )
                    """
                ),
                {
                    "id": workflow_def_id,
                    "tenant_id": tenant_id,
                    "company_id": company_id,
                    "request_type_id": request_type_id,
                    "name": "Smoke Approval Flow",
                    "created_by": requester_user_id,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO workflow.workflow_definition_steps (
                      workflow_definition_id, step_order, approver_mode, role_code, user_id
                    ) VALUES (
                      :workflow_definition_id, 1, 'ROLE', 'HR_MANAGER', NULL
                    )
                    """
                ),
                {"workflow_definition_id": workflow_def_id},
            )

            conn.execute(
                text(
                    """
                    INSERT INTO workflow.requests (
                      id, tenant_id, company_id, branch_id, request_type_id, workflow_definition_id,
                      requester_employee_id, subject, status, current_step, payload
                    ) VALUES (
                      :id, :tenant_id, :company_id, :branch_id, :request_type_id, :workflow_definition_id,
                      :requester_employee_id, :subject, 'submitted', 1, CAST(:payload AS jsonb)
                    )
                    """
                ),
                {
                    "id": request_id,
                    "tenant_id": tenant_id,
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "request_type_id": request_type_id,
                    "workflow_definition_id": workflow_def_id,
                    "requester_employee_id": employee_id,
                    "subject": "Smoke Test Request",
                    "payload": '{"kind":"smoke","notes":"hello"}',
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO workflow.request_steps (
                      id, request_id, step_order, approver_user_id, decision, decided_at, comment
                    ) VALUES (
                      :id, :request_id, 1, :approver_user_id, 'approved', now(), 'ok'
                    )
                    """
                ),
                {
                    "id": request_step_id,
                    "request_id": request_id,
                    "approver_user_id": approver_user_id,
                },
            )

            # ------------------------------------------------------------------
            # dms + attachment
            # ------------------------------------------------------------------
            conn.execute(
                text(
                    """
                    INSERT INTO dms.files (
                      id, tenant_id, storage_provider, bucket, object_key, content_type,
                      size_bytes, sha256, original_filename
                    ) VALUES (
                      :id, :tenant_id, 'local', NULL, :object_key, 'application/octet-stream',
                      0, NULL, 'smoke.txt'
                    )
                    """
                ),
                {
                    "id": file_id,
                    "tenant_id": tenant_id,
                    "object_key": f"smoke/{file_id.hex}/smoke.txt",
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO workflow.request_attachments (
                      id, tenant_id, request_id, file_id, created_by
                    ) VALUES (
                      :id, :tenant_id, :request_id, :file_id, :created_by
                    )
                    """
                ),
                {
                    "id": attachment_id,
                    "tenant_id": tenant_id,
                    "request_id": request_id,
                    "file_id": file_id,
                    "created_by": requester_user_id,
                },
            )

            # ------------------------------------------------------------------
            # Rewiring validation (module schemas -> vNext masters)
            # ------------------------------------------------------------------
            # Attendance: verify attendance_daily uses branch_id
            # and employee_id references hr_core.employees.
            if _table_exists(conn, "attendance", "attendance_daily"):
                if not _column_exists(conn, "attendance", "attendance_daily", "branch_id"):
                    _warn("attendance.attendance_daily missing branch_id; skipping insert")
                else:
                    cols = ["id", "branch_id", "business_date", "employee_id"]
                    vals = [":id", ":branch_id", ":business_date", ":employee_id"]
                    params = {
                        "id": uuid4(),
                        "branch_id": branch_id,
                        "business_date": today,
                        "employee_id": employee_id,
                    }
                    if _column_exists(conn, "attendance", "attendance_daily", "tenant_id"):
                        cols.insert(1, "tenant_id")
                        vals.insert(1, ":tenant_id")
                        params["tenant_id"] = tenant_id
                    conn.execute(
                        text(
                            f"""
                            INSERT INTO attendance.attendance_daily ({", ".join(cols)})
                            VALUES ({", ".join(vals)})
                            """
                        ),
                        params,
                    )
            else:
                _warn("attendance.attendance_daily not found; skipping attendance rewiring check")

            # Face: verify employee_faces.employee_id references hr_core.employees.
            if _table_exists(conn, "face", "employee_faces"):
                if _column_exists(conn, "face", "employee_faces", "tenant_id"):
                    conn.execute(
                        text(
                            """
                            INSERT INTO face.employee_faces (id, tenant_id, employee_id, embedding, model_version)
                            VALUES (
                              :id, :tenant_id, :employee_id, array_fill(0::real, ARRAY[512])::vector, 'smoke'
                            )
                            """
                        ),
                        {"id": uuid4(), "tenant_id": tenant_id, "employee_id": employee_id},
                    )
                else:
                    conn.execute(
                        text(
                            """
                            INSERT INTO face.employee_faces (id, employee_id, embedding, model_version)
                            VALUES (
                              :id, :employee_id, array_fill(0::real, ARRAY[512])::vector, 'smoke'
                            )
                            """
                        ),
                        {"id": uuid4(), "employee_id": employee_id},
                    )
            else:
                _warn("face.employee_faces not found; skipping face rewiring check")

            # ------------------------------------------------------------------
            # Tenant/scope column checks for critical tables.
            # ------------------------------------------------------------------
            critical_columns = {
                ("tenancy", "companies"): ["tenant_id"],
                ("tenancy", "branches"): ["tenant_id", "company_id"],
                ("iam", "user_roles"): ["tenant_id", "company_id", "branch_id"],
                ("hr_core", "persons"): ["tenant_id"],
                ("hr_core", "employees"): ["tenant_id", "company_id"],
                ("hr_core", "employee_employment"): ["tenant_id", "company_id", "branch_id"],
                ("workflow", "workflow_definitions"): ["tenant_id", "company_id"],
                ("workflow", "requests"): ["tenant_id", "company_id", "branch_id"],
                ("dms", "files"): ["tenant_id"],
                ("dms", "document_types"): ["tenant_id"],
                ("dms", "documents"): ["tenant_id"],
                ("roster", "shift_templates"): ["tenant_id", "branch_id"],
                ("roster", "branch_defaults"): ["tenant_id", "branch_id"],
                ("roster", "shift_assignments"): ["tenant_id", "branch_id", "employee_id"],
                ("roster", "roster_overrides"): ["tenant_id", "branch_id", "employee_id"],
                ("attendance", "payable_day_summaries"): ["tenant_id", "branch_id", "employee_id"],
                ("payroll", "calendars"): ["tenant_id"],
                ("payroll", "periods"): ["tenant_id", "calendar_id"],
                ("payroll", "components"): ["tenant_id"],
                ("payroll", "salary_structures"): ["tenant_id"],
                ("payroll", "employee_compensations"): [
                    "tenant_id",
                    "employee_id",
                    "salary_structure_id",
                ],
                ("payroll", "payruns"): ["tenant_id", "branch_id", "calendar_id"],
                ("payroll", "payslips"): ["tenant_id", "employee_id", "payrun_id"],
            }
            for (schema, table), columns in critical_columns.items():
                if _table_exists(conn, schema, table):
                    _assert_required_columns(conn, schema, table, columns)

            # ------------------------------------------------------------------
            # Index checks (keeps this lightweight; fail only on critical misses).
            # ------------------------------------------------------------------
            _assert_index(conn, "workflow", "ix_requests_tenant_status_type_created_at")
            _assert_index(conn, "workflow", "ix_request_steps_approver_decided_at")
            _assert_index(conn, "workflow", "ix_request_steps_approver_pending")
            _assert_index(conn, "workflow", "ix_requests_requester_created_at")
            _assert_index(conn, "workflow", "ix_notification_outbox_tenant_status_retry")
            _assert_index(conn, "dms", "ix_documents_tenant_expires_at")
            _assert_index(conn, "dms", "ix_document_links_tenant_entity")
            _assert_index(conn, "dms", "ix_document_types_tenant_is_active")
            _assert_index(conn, "dms", "ix_documents_tenant_owner")
            _assert_index(conn, "dms", "ix_documents_tenant_status")
            _assert_index(conn, "dms", "ix_document_versions_tenant_doc_created_at")
            _assert_index(conn, "dms", "ix_expiry_events_tenant_notify_on_date")
            _assert_index(conn, "hr_core", "ix_employee_government_ids_tenant_expires_at")
            _assert_index(conn, "iam", "uq_users_email_not_deleted")
            _assert_index(conn, "roster", "ix_shift_assignments_employee_effective_from")
            _assert_index(conn, "roster", "ix_shift_assignments_branch_effective_from")
            _assert_index(conn, "roster", "ix_roster_overrides_branch_day")
            _assert_index(conn, "attendance", "ix_payable_day_summaries_branch_day")
            _assert_index(conn, "attendance", "ix_payable_day_summaries_employee_day")
            _assert_index(conn, "payroll", "ix_payroll_calendars_tenant_active")
            _assert_index(conn, "payroll", "ix_payroll_periods_tenant_dates")
            _assert_index(conn, "payroll", "ix_payroll_components_tenant_type_active")
            _assert_index(conn, "payroll", "ix_payroll_salary_structures_tenant_active")
            _assert_index(
                conn, "payroll", "ix_payroll_employee_compensations_employee_effective_from"
            )
            _assert_index(conn, "payroll", "ix_payroll_payruns_tenant_period_status")
            _assert_index(conn, "payroll", "ix_payroll_payrun_items_payrun")
            _assert_index(conn, "payroll", "ix_payroll_payrun_items_employee")
            _assert_index(conn, "payroll", "ix_payroll_payrun_item_lines_item")
            _assert_index(conn, "payroll", "ix_payroll_payslips_employee_created_at")
        finally:
            # Keep the smoke test safe to run on every startup.
            tx.rollback()

    print("DB vNext smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
