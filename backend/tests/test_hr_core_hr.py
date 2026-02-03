from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping API integration tests",
)


def _make_app():
    from fastapi import FastAPI

    from app.auth.router import router as auth_router
    from app.core.errors import install_exception_handlers
    from app.core.middleware.trace import TraceIdMiddleware
    from app.domains.hr_core.router_ess import router as ess_router
    from app.domains.hr_core.router_hr import router as hr_router

    app = FastAPI()
    app.add_middleware(TraceIdMiddleware)
    install_exception_handlers(app)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(hr_router, prefix="/api/v1")
    app.include_router(ess_router, prefix="/api/v1")
    return app


def _require_vnext(conn) -> None:
    for fqtn in (
        "tenancy.tenants",
        "tenancy.companies",
        "tenancy.branches",
        "iam.users",
        "iam.roles",
        "iam.user_roles",
        "hr_core.persons",
        "hr_core.employees",
        "hr_core.employee_employment",
        "hr_core.employee_user_links",
    ):
        exists = conn.execute(text("SELECT to_regclass(:fqtn)"), {"fqtn": fqtn}).scalar()
        assert exists is not None, f"Missing required table {fqtn}; did you run migrations?"


def _role_id(conn, code: str) -> uuid.UUID:
    rid = conn.execute(text("SELECT id FROM iam.roles WHERE code = :code"), {"code": code}).scalar()
    assert rid is not None, f"Missing IAM role {code}; ensure seed migrations ran."
    return rid


def _seed_tenant_admin(engine) -> dict[str, str]:
    tenant_id = uuid.uuid4()
    company_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    user_id = uuid.uuid4()

    admin_email = f"admin-hrcore+{user_id.hex[:10]}@example.com"
    admin_password = "StrongPass123"

    from app.auth.passwords import hash_password

    with engine.begin() as conn:
        _require_vnext(conn)

        conn.execute(
            text("INSERT INTO tenancy.tenants (id, name, status) VALUES (:id, :name, 'ACTIVE')"),
            {"id": tenant_id, "name": f"Tenant {tenant_id.hex[:6]}"},
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
                "name": f"Company {company_id.hex[:6]}",
                "legal_name": f"Company {company_id.hex[:6]} LLC",
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
                "name": "HQ",
                "code": f"HQ{branch_id.hex[:4].upper()}",
            },
        )

        conn.execute(
            text(
                """
                INSERT INTO iam.users (id, email, phone, password_hash, status)
                VALUES (:id, :email, NULL, :password_hash, 'ACTIVE')
                """
            ),
            {"id": user_id, "email": admin_email, "password_hash": hash_password(admin_password)},
        )
        conn.execute(
            text(
                """
                INSERT INTO iam.user_roles (user_id, tenant_id, company_id, branch_id, role_id)
                VALUES (:user_id, :tenant_id, :company_id, :branch_id, :role_id)
                """
            ),
            {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "company_id": company_id,
                "branch_id": branch_id,
                "role_id": _role_id(conn, "ADMIN"),
            },
        )

    return {
        "tenant_id": str(tenant_id),
        "company_id": str(company_id),
        "branch_id": str(branch_id),
        "admin_user_id": str(user_id),
        "admin_email": admin_email,
        "admin_password": admin_password,
    }


def _cleanup(engine, *, tenant_id: str, user_ids: list[str]) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM tenancy.tenants WHERE id = :id"), {"id": tenant_id})
    if user_ids:
        with engine.begin() as conn:
            for uid in user_ids:
                conn.execute(text("DELETE FROM iam.users WHERE id = :id"), {"id": uid})


def test_hr_create_employee_and_directory() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    seed = _seed_tenant_admin(engine)
    created_users = [seed["admin_user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(_make_app())
        login = client.post("/api/v1/auth/login", json={"email": seed["admin_email"], "password": seed["admin_password"]})
        assert login.status_code == 200, login.text
        token = login.json()["data"]["access_token"]

        payload = {
            "person": {"first_name": "Alice", "last_name": "One", "email": "alice.one@example.com", "address": {}},
            "employee": {
                "company_id": seed["company_id"],
                "employee_code": f"E{uuid.uuid4().hex[:6].upper()}",
                "join_date": str(date(2026, 1, 1)),
                "status": "ACTIVE",
            },
            "employment": {"start_date": str(date(2026, 1, 1)), "branch_id": seed["branch_id"], "is_primary": True},
        }

        created = client.post(
            "/api/v1/hr/employees",
            headers={"Authorization": f"Bearer {token}"},
            json=payload,
        )
        assert created.status_code == 200, created.text
        body = created.json()
        assert body["ok"] is True
        employee_id = body["data"]["employee"]["id"]

        directory = client.get(
            "/api/v1/hr/employees",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": payload["employee"]["employee_code"]},
        )
        assert directory.status_code == 200, directory.text
        items = directory.json()["data"]["items"]
        assert any(r["employee_id"] == employee_id for r in items)

        details = client.get(
            f"/api/v1/hr/employees/{employee_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert details.status_code == 200, details.text
        assert details.json()["data"]["employee"]["employee_code"] == payload["employee"]["employee_code"]
    finally:
        _cleanup(engine, tenant_id=seed["tenant_id"], user_ids=created_users)


def test_hr_employment_change_and_cycle_prevention() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    seed = _seed_tenant_admin(engine)
    created_users = [seed["admin_user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(_make_app())
        login = client.post("/api/v1/auth/login", json={"email": seed["admin_email"], "password": seed["admin_password"]})
        assert login.status_code == 200, login.text
        token = login.json()["data"]["access_token"]

        # Create manager A (no manager).
        a_payload = {
            "person": {"first_name": "Manager", "last_name": "A", "address": {}},
            "employee": {"company_id": seed["company_id"], "employee_code": f"A{uuid.uuid4().hex[:6].upper()}", "status": "ACTIVE"},
            "employment": {"start_date": str(date(2026, 1, 1)), "branch_id": seed["branch_id"], "is_primary": True},
        }
        a = client.post("/api/v1/hr/employees", headers={"Authorization": f"Bearer {token}"}, json=a_payload)
        assert a.status_code == 200, a.text
        a_id = a.json()["data"]["employee"]["id"]

        # Create employee B with manager A.
        b_payload = {
            "person": {"first_name": "Employee", "last_name": "B", "address": {}},
            "employee": {"company_id": seed["company_id"], "employee_code": f"B{uuid.uuid4().hex[:6].upper()}", "status": "ACTIVE"},
            "employment": {
                "start_date": str(date(2026, 1, 1)),
                "branch_id": seed["branch_id"],
                "manager_employee_id": a_id,
                "is_primary": True,
            },
        }
        b = client.post("/api/v1/hr/employees", headers={"Authorization": f"Bearer {token}"}, json=b_payload)
        assert b.status_code == 200, b.text
        b_id = b.json()["data"]["employee"]["id"]

        # Attempt to make A report to B -> should create a cycle (B -> A -> B).
        change = client.post(
            f"/api/v1/hr/employees/{a_id}/employment",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "start_date": str(date(2026, 2, 1)),
                "branch_id": seed["branch_id"],
                "manager_employee_id": b_id,
            },
        )
        assert change.status_code == 400, change.text
        body = change.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "hr.manager.cycle"
    finally:
        _cleanup(engine, tenant_id=seed["tenant_id"], user_ids=created_users)

