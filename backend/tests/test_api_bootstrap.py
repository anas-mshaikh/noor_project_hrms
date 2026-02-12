from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text

from tests.helpers.app import make_app
from tests.helpers.seed import cleanup


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping API integration tests",
)


def test_bootstrap_happy_path() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    with engine.connect() as conn:
        exists = conn.execute(text("SELECT to_regclass('tenancy.tenants')")).scalar()
        assert exists is not None, "Missing DB vNext schemas; run migrations first."

        tenant_count = int(conn.execute(text("SELECT COUNT(*) FROM tenancy.tenants")).scalar() or 0)
        if tenant_count != 0:
            pytest.skip("Bootstrap requires a fresh DB (no tenants). Reset DB volume to run this test.")

    from fastapi.testclient import TestClient

    client = TestClient(make_app("app.domains.tenancy.router"))

    payload = {
        "tenant_name": "Bootstrap Tenant",
        "company_name": "Bootstrap Company",
        "branch_name": "HQ",
        "branch_code": "HQ",
        "timezone": "Asia/Riyadh",
        "currency_code": "SAR",
        "admin_email": "admin@bootstrap.example.com",
        "admin_password": "StrongPass123",
    }

    tenant_id = None
    user_id = None

    try:
        r = client.post("/api/v1/bootstrap", json=payload)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["ok"] is True
        data = body["data"]
        assert data["access_token"]
        assert data["refresh_token"]
        assert "ADMIN" in data["roles"]

        tenant_id = data["scope"]["tenant_id"]
        company_id = data["scope"]["company_id"]
        branch_id = data["scope"]["branch_id"]
        user_id = data["user"]["id"]

        with engine.connect() as conn:
            t = conn.execute(text("SELECT id FROM tenancy.tenants WHERE id = :id"), {"id": tenant_id}).first()
            assert t is not None
            c = conn.execute(text("SELECT id FROM tenancy.companies WHERE id = :id"), {"id": company_id}).first()
            assert c is not None
            b = conn.execute(text("SELECT id FROM tenancy.branches WHERE id = :id"), {"id": branch_id}).first()
            assert b is not None
            u = conn.execute(text("SELECT id, email FROM iam.users WHERE id = :id"), {"id": user_id}).first()
            assert u is not None
            assert u.email == payload["admin_email"]

            roles = conn.execute(
                text(
                    """
                    SELECT r.code
                    FROM iam.user_roles ur
                    JOIN iam.roles r ON r.id = ur.role_id
                    WHERE ur.user_id = :user_id
                    """
                ),
                {"user_id": user_id},
            ).scalars().all()
            assert "ADMIN" in set(roles)

            rt = conn.execute(
                text("SELECT 1 FROM iam.refresh_tokens WHERE user_id = :user_id AND revoked_at IS NULL"),
                {"user_id": user_id},
            ).first()
            assert rt is not None
    finally:
        # Keep bootstrap test safe to re-run if it executed.
        cleanup(engine, tenant_id=tenant_id, user_ids=[user_id] if user_id is not None else [])
