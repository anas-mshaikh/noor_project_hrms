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

    app = FastAPI()
    app.add_middleware(TraceIdMiddleware)
    install_exception_handlers(app)
    app.include_router(auth_router, prefix="/api/v1")
    return app


def _require_vnext_tables(conn) -> None:
    required = [
        "tenancy.tenants",
        "tenancy.companies",
        "tenancy.branches",
        "iam.users",
        "iam.roles",
        "iam.user_roles",
        "iam.refresh_tokens",
    ]
    for fqtn in required:
        exists = conn.execute(text("SELECT to_regclass(:fqtn)"), {"fqtn": fqtn}).scalar()
        assert exists is not None, f"Missing required table {fqtn}; did you run Alembic migrations?"


def test_login_refresh_logout_rotation() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant_id = uuid.uuid4()
    company_id = uuid.uuid4()
    branch_id = uuid.uuid4()
    user_id = uuid.uuid4()

    email = f"test-admin+{user_id.hex[:10]}@example.com"
    password = "StrongPass123"

    from app.auth.passwords import hash_password

    try:
        with engine.begin() as conn:
            _require_vnext_tables(conn)

            role_id = conn.execute(text("SELECT id FROM iam.roles WHERE code = 'ADMIN'")).scalar()
            assert role_id is not None, "Missing IAM role ADMIN; ensure seed migration 0002 ran."

            conn.execute(
                text("INSERT INTO tenancy.tenants (id, name, status) VALUES (:id, :name, 'ACTIVE')"),
                {"id": tenant_id, "name": f"Test Tenant {tenant_id.hex[:6]}"},
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
                    "name": f"Test Company {company_id.hex[:6]}",
                    "legal_name": f"Test Company {company_id.hex[:6]} LLC",
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
                    "role_id": role_id,
                },
            )

        from fastapi.testclient import TestClient

        client = TestClient(_make_app())

        r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        tokens = body["data"]
        assert tokens["access_token"]
        assert tokens["refresh_token"]

        r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
        assert r2.status_code == 200, r2.text
        body2 = r2.json()
        assert body2["ok"] is True
        tokens2 = body2["data"]
        assert tokens2["access_token"]
        assert tokens2["refresh_token"]
        assert tokens2["refresh_token"] != tokens["refresh_token"], "refresh token must rotate"

        r3 = client.post("/api/v1/auth/logout", json={"refresh_token": tokens2["refresh_token"]})
        assert r3.status_code == 200, r3.text
        body3 = r3.json()
        assert body3["ok"] is True
        assert body3["data"]["revoked"] is True

        r4 = client.post("/api/v1/auth/refresh", json={"refresh_token": tokens2["refresh_token"]})
        assert r4.status_code == 401
        body4 = r4.json()
        assert body4["ok"] is False
        assert body4["error"]["code"] in {"invalid_refresh_token", "refresh_token_expired"}
    finally:
        # Keep tests safe to rerun: delete created rows.
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM tenancy.tenants WHERE id = :id"), {"id": tenant_id})
            conn.execute(text("DELETE FROM iam.users WHERE id = :id"), {"id": user_id})
