from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping API integration tests",
)


from tests.helpers.app import make_app
from tests.helpers.http import login
from tests.helpers.seed import cleanup, require_tables, seed_tenant_company, seed_user


def test_login_refresh_logout_rotation() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="test-admin",
    )
    try:
        with engine.begin() as conn:
            require_tables(
                conn,
                "tenancy.tenants",
                "tenancy.companies",
                "tenancy.branches",
                "iam.users",
                "iam.roles",
                "iam.user_roles",
                "iam.refresh_tokens",
            )

        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router"))

        tokens = login(client, email=admin["email"], password=admin["password"])
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
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"]])
