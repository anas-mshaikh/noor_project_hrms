from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping API integration tests",
)

from tests.helpers.app import make_app
from tests.helpers.http import login
from tests.helpers.seed import cleanup, seed_tenant_company, seed_user


def test_create_branch_requires_admin() -> None:
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
    employee = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="test-employee",
    )

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.tenancy.router"))

        admin_tokens = login(client, email=admin["email"], password=admin["password"])
        employee_tokens = login(client, email=employee["email"], password=employee["password"])

        new_branch_code = f"TST{uuid.uuid4().hex[:6].upper()}"
        payload = {
            "company_id": tenant["company_id"],
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
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"], employee["user_id"]])
