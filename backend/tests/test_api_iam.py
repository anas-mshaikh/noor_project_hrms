from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from tests.helpers.app import make_app
from tests.helpers.seed import cleanup


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping API integration tests",
)

def _assert_fresh_db(engine) -> None:
    with engine.connect() as conn:
        exists = conn.execute(text("SELECT to_regclass('tenancy.tenants')")).scalar()
        assert exists is not None, "Missing DB vNext schemas; run Alembic migrations first."

        tenants = int(conn.execute(text("SELECT COUNT(*) FROM tenancy.tenants")).scalar() or 0)
        if tenants != 0:
            pytest.skip("IAM integration tests require a fresh DB (no tenants). Reset DB volume to run.")


def test_bootstrap_then_create_user_and_login() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)
    _assert_fresh_db(engine)

    from fastapi.testclient import TestClient

    client = TestClient(make_app("app.auth.router", "app.domains.tenancy.router", "app.domains.iam.router"))

    admin_email = f"admin+{uuid.uuid4().hex[:8]}@example.com"
    hr_email = f"hr+{uuid.uuid4().hex[:8]}@example.com"

    tenant_id: str | None = None
    created_users: list[str] = []

    try:
        boot = client.post(
            "/api/v1/bootstrap",
            json={
                "tenant_name": "T",
                "company_name": "C",
                "branch_name": "HQ",
                "branch_code": "HQ",
                "timezone": "Asia/Riyadh",
                "currency_code": "SAR",
                "admin_email": admin_email,
                "admin_password": "StrongPass123",
            },
        )
        assert boot.status_code == 200, boot.text
        admin = boot.json()["data"]
        tenant_id = admin["scope"]["tenant_id"]
        created_users.append(admin["user"]["id"])

        admin_access = admin["access_token"]

        cu = client.post(
            "/api/v1/iam/users",
            headers={"Authorization": f"Bearer {admin_access}"},
            json={"email": hr_email, "password": "HrPass12345", "status": "ACTIVE"},
        )
        assert cu.status_code == 200, cu.text
        hr_user = cu.json()["data"]
        created_users.append(hr_user["id"])

        login = client.post("/api/v1/auth/login", json={"email": hr_email, "password": "HrPass12345"})
        assert login.status_code == 200, login.text
        assert login.json()["ok"] is True
    finally:
        cleanup(engine, tenant_id=tenant_id, user_ids=created_users)


def test_assign_role_scoped_and_enforced_scope_headers() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)
    _assert_fresh_db(engine)

    from fastapi.testclient import TestClient

    client = TestClient(make_app("app.auth.router", "app.domains.tenancy.router", "app.domains.iam.router"))

    admin_email = f"admin+{uuid.uuid4().hex[:8]}@example.com"
    hr_email = f"hr+{uuid.uuid4().hex[:8]}@example.com"

    tenant_id: str | None = None
    created_users: list[str] = []

    try:
        boot = client.post(
            "/api/v1/bootstrap",
            json={
                "tenant_name": "T",
                "company_name": "C",
                "branch_name": "HQ",
                "branch_code": "HQ",
                "timezone": "Asia/Riyadh",
                "currency_code": "SAR",
                "admin_email": admin_email,
                "admin_password": "StrongPass123",
            },
        )
        assert boot.status_code == 200, boot.text
        admin = boot.json()["data"]
        tenant_id = admin["scope"]["tenant_id"]
        company_id = admin["scope"]["company_id"]
        branch1_id = admin["scope"]["branch_id"]
        created_users.append(admin["user"]["id"])
        admin_access = admin["access_token"]

        cu = client.post(
            "/api/v1/iam/users",
            headers={"Authorization": f"Bearer {admin_access}"},
            json={"email": hr_email, "password": "HrPass12345", "status": "ACTIVE"},
        )
        assert cu.status_code == 200, cu.text
        hr_user_id = cu.json()["data"]["id"]
        created_users.append(hr_user_id)

        # Create a second branch.
        b2 = client.post(
            "/api/v1/tenancy/branches",
            headers={"Authorization": f"Bearer {admin_access}"},
            json={
                "company_id": company_id,
                "name": "Branch 2",
                "code": f"B2{uuid.uuid4().hex[:4].upper()}",
                "timezone": "Asia/Riyadh",
                "address": {},
            },
        )
        assert b2.status_code == 200, b2.text
        branch2_id = b2.json()["data"]["id"]

        # Assign HR_ADMIN scoped to branch1 only (company inferred from branch).
        ar = client.post(
            f"/api/v1/iam/users/{hr_user_id}/roles",
            headers={"Authorization": f"Bearer {admin_access}"},
            json={"role_code": "HR_ADMIN", "branch_id": branch1_id},
        )
        assert ar.status_code == 200, ar.text

        # Login as HR user.
        login = client.post("/api/v1/auth/login", json={"email": hr_email, "password": "HrPass12345"})
        assert login.status_code == 200, login.text
        hr_access = login.json()["data"]["access_token"]

        # Allowed branch header should pass.
        ok_resp = client.get(
            f"/api/v1/tenancy/branches?company_id={company_id}",
            headers={"Authorization": f"Bearer {hr_access}", "X-Branch-Id": branch1_id},
        )
        assert ok_resp.status_code == 200, ok_resp.text

        # Forbidden branch header should be rejected by scope resolver.
        bad = client.get(
            f"/api/v1/tenancy/branches?company_id={company_id}",
            headers={"Authorization": f"Bearer {hr_access}", "X-Branch-Id": branch2_id},
        )
        assert bad.status_code == 403, bad.text
        body = bad.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "iam.scope.forbidden"
    finally:
        cleanup(engine, tenant_id=tenant_id, user_ids=created_users)


def test_disable_user_blocks_login_and_refresh() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)
    _assert_fresh_db(engine)

    from fastapi.testclient import TestClient

    client = TestClient(make_app("app.auth.router", "app.domains.tenancy.router", "app.domains.iam.router"))

    admin_email = f"admin+{uuid.uuid4().hex[:8]}@example.com"
    hr_email = f"hr+{uuid.uuid4().hex[:8]}@example.com"

    tenant_id: str | None = None
    created_users: list[str] = []

    try:
        boot = client.post(
            "/api/v1/bootstrap",
            json={
                "tenant_name": "T",
                "company_name": "C",
                "branch_name": "HQ",
                "branch_code": "HQ",
                "timezone": "Asia/Riyadh",
                "currency_code": "SAR",
                "admin_email": admin_email,
                "admin_password": "StrongPass123",
            },
        )
        assert boot.status_code == 200, boot.text
        admin = boot.json()["data"]
        tenant_id = admin["scope"]["tenant_id"]
        admin_access = admin["access_token"]
        created_users.append(admin["user"]["id"])

        cu = client.post(
            "/api/v1/iam/users",
            headers={"Authorization": f"Bearer {admin_access}"},
            json={"email": hr_email, "password": "HrPass12345", "status": "ACTIVE"},
        )
        assert cu.status_code == 200, cu.text
        hr_user_id = cu.json()["data"]["id"]
        created_users.append(hr_user_id)

        login = client.post("/api/v1/auth/login", json={"email": hr_email, "password": "HrPass12345"})
        assert login.status_code == 200, login.text
        refresh_token = login.json()["data"]["refresh_token"]

        # Disable the user.
        patch = client.patch(
            f"/api/v1/iam/users/{hr_user_id}",
            headers={"Authorization": f"Bearer {admin_access}"},
            json={"status": "DISABLED"},
        )
        assert patch.status_code == 200, patch.text

        login2 = client.post("/api/v1/auth/login", json={"email": hr_email, "password": "HrPass12345"})
        assert login2.status_code == 401
        assert login2.json()["ok"] is False

        refresh2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert refresh2.status_code == 401
        assert refresh2.json()["ok"] is False
        assert refresh2.json()["error"]["code"] == "unauthorized"
    finally:
        cleanup(engine, tenant_id=tenant_id, user_ids=created_users)
