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


def _role_id(conn, code: str) -> uuid.UUID:
    rid = conn.execute(text("SELECT id FROM iam.roles WHERE code = :code"), {"code": code}).scalar()
    assert rid is not None, f"Missing IAM role {code}; ensure seed migrations ran."
    return rid


def _seed_tenant(engine) -> dict[str, str]:
    tenant_id = uuid.uuid4()
    company_id = uuid.uuid4()
    branch_id = uuid.uuid4()

    with engine.begin() as conn:
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

    return {"tenant_id": str(tenant_id), "company_id": str(company_id), "branch_id": str(branch_id)}


def _seed_user(engine, *, tenant_id: str, company_id: str, branch_id: str, role_code: str) -> dict[str, str]:
    user_id = uuid.uuid4()
    email = f"user-ess+{user_id.hex[:10]}@example.com"
    password = "StrongPass123"

    from app.auth.passwords import hash_password

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO iam.users (id, email, phone, password_hash, status)
                VALUES (:id, :email, NULL, :password_hash, 'ACTIVE')
                """
            ),
            {"id": user_id, "email": email, "password_hash": hash_password(password)},
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
                "role_id": _role_id(conn, role_code),
            },
        )

    return {"user_id": str(user_id), "email": email, "password": password}


def _cleanup(engine, *, tenant_id: str, user_ids: list[str]) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM tenancy.tenants WHERE id = :id"), {"id": tenant_id})
    if user_ids:
        with engine.begin() as conn:
            for uid in user_ids:
                conn.execute(text("DELETE FROM iam.users WHERE id = :id"), {"id": uid})


def test_ess_profile_requires_link() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = _seed_tenant(engine)
    user = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE")

    try:
        from fastapi.testclient import TestClient

        client = TestClient(_make_app())
        login = client.post("/api/v1/auth/login", json={"email": user["email"], "password": user["password"]})
        assert login.status_code == 200, login.text
        token = login.json()["data"]["access_token"]

        me = client.get("/api/v1/ess/me/profile", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 409, me.text
        body = me.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "ess.not_linked"
    finally:
        _cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[user["user_id"]])


def test_ess_profile_after_link_and_safe_patch() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = _seed_tenant(engine)
    admin = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN")
    employee_user = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE")

    created_users = [admin["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(_make_app())

        admin_login = client.post("/api/v1/auth/login", json={"email": admin["email"], "password": admin["password"]})
        assert admin_login.status_code == 200, admin_login.text
        admin_token = admin_login.json()["data"]["access_token"]

        # Create an employee record.
        emp_payload = {
            "person": {"first_name": "ESS", "last_name": "User", "email": employee_user["email"], "address": {}},
            "employee": {"company_id": tenant["company_id"], "employee_code": f"ESS{uuid.uuid4().hex[:5].upper()}", "join_date": str(date(2026, 1, 1)), "status": "ACTIVE"},
            "employment": {"start_date": str(date(2026, 1, 1)), "branch_id": tenant["branch_id"], "is_primary": True},
        }
        created = client.post("/api/v1/hr/employees", headers={"Authorization": f"Bearer {admin_token}"}, json=emp_payload)
        assert created.status_code == 200, created.text
        employee_id = created.json()["data"]["employee"]["id"]

        # Link IAM user to employee.
        link = client.post(
            f"/api/v1/hr/employees/{employee_id}/link-user",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"user_id": employee_user["user_id"]},
        )
        assert link.status_code == 200, link.text

        emp_login = client.post("/api/v1/auth/login", json={"email": employee_user["email"], "password": employee_user["password"]})
        assert emp_login.status_code == 200, emp_login.text
        emp_token = emp_login.json()["data"]["access_token"]

        me = client.get("/api/v1/ess/me/profile", headers={"Authorization": f"Bearer {emp_token}"})
        assert me.status_code == 200, me.text
        assert me.json()["data"]["employee"]["employee_code"] == emp_payload["employee"]["employee_code"]

        patched = client.patch(
            "/api/v1/ess/me/profile",
            headers={"Authorization": f"Bearer {emp_token}"},
            json={"phone": "5550001", "address": {"line1": "Street 1"}},
        )
        assert patched.status_code == 200, patched.text
        assert patched.json()["data"]["person"]["phone"] == "5550001"
        assert patched.json()["data"]["person"]["address"]["line1"] == "Street 1"

        bad = client.patch(
            "/api/v1/ess/me/profile",
            headers={"Authorization": f"Bearer {emp_token}"},
            json={"employee_code": "HACKED"},
        )
        assert bad.status_code == 400, bad.text
        body = bad.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "ess.profile.invalid_field"
    finally:
        _cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)

