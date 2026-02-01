from __future__ import annotations

import os
import uuid

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
    from app.domains.tenancy.router import router as tenancy_router

    app = FastAPI()
    app.add_middleware(TraceIdMiddleware)
    install_exception_handlers(app)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(tenancy_router, prefix="/api/v1")
    return app


def _role_id(conn, code: str) -> uuid.UUID:
    rid = conn.execute(text("SELECT id FROM iam.roles WHERE code = :code"), {"code": code}).scalar()
    assert rid is not None, f"Missing IAM role {code}; ensure seed migration 0002 ran."
    return rid


def test_create_branch_requires_admin() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant_id = uuid.uuid4()
    company_id = uuid.uuid4()
    branch_id = uuid.uuid4()

    admin_user_id = uuid.uuid4()
    employee_user_id = uuid.uuid4()

    admin_email = f"test-admin+{admin_user_id.hex[:10]}@example.com"
    employee_email = f"test-employee+{employee_user_id.hex[:10]}@example.com"
    password = "StrongPass123"

    from app.auth.passwords import hash_password

    try:
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
                    "code": f"HQ{branch_id.hex[:3].upper()}",
                },
            )

            conn.execute(
                text(
                    """
                    INSERT INTO iam.users (id, email, phone, password_hash, status)
                    VALUES (:id, :email, NULL, :password_hash, 'ACTIVE')
                    """
                ),
                {"id": admin_user_id, "email": admin_email, "password_hash": hash_password(password)},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO iam.users (id, email, phone, password_hash, status)
                    VALUES (:id, :email, NULL, :password_hash, 'ACTIVE')
                    """
                ),
                {"id": employee_user_id, "email": employee_email, "password_hash": hash_password(password)},
            )

            conn.execute(
                text(
                    """
                    INSERT INTO iam.user_roles (user_id, tenant_id, company_id, branch_id, role_id)
                    VALUES (:user_id, :tenant_id, :company_id, :branch_id, :role_id)
                    """
                ),
                {
                    "user_id": admin_user_id,
                    "tenant_id": tenant_id,
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "role_id": _role_id(conn, "ADMIN"),
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
                    "user_id": employee_user_id,
                    "tenant_id": tenant_id,
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "role_id": _role_id(conn, "EMPLOYEE"),
                },
            )

        from fastapi.testclient import TestClient

        client = TestClient(_make_app())

        admin_login = client.post("/api/v1/auth/login", json={"email": admin_email, "password": password})
        assert admin_login.status_code == 200, admin_login.text
        admin_tokens = admin_login.json()["data"]

        employee_login = client.post("/api/v1/auth/login", json={"email": employee_email, "password": password})
        assert employee_login.status_code == 200, employee_login.text
        employee_tokens = employee_login.json()["data"]

        new_branch_code = f"TST{uuid.uuid4().hex[:6].upper()}"
        payload = {
            "company_id": str(company_id),
            "name": "Test Branch",
            "code": new_branch_code,
            "timezone": "Asia/Riyadh",
            "address": {},
        }

        r_ok = client.post(
            "/api/v1/tenancy/branches",
            headers={"Authorization": f"Bearer {admin_tokens['access_token']}"},
            json=payload,
        )
        assert r_ok.status_code == 200, r_ok.text
        assert r_ok.json()["ok"] is True

        r_forbidden = client.post(
            "/api/v1/tenancy/branches",
            headers={"Authorization": f"Bearer {employee_tokens['access_token']}"},
            json=payload,
        )
        assert r_forbidden.status_code == 403
        assert r_forbidden.json()["ok"] is False
        assert r_forbidden.json()["error"]["code"] == "forbidden"
    finally:
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM tenancy.tenants WHERE id = :id"), {"id": tenant_id})
            conn.execute(text("DELETE FROM iam.users WHERE id IN (:a, :b)"), {"a": admin_user_id, "b": employee_user_id})
