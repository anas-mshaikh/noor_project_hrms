from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping API integration tests",
)

from tests.helpers.app import make_app
from tests.helpers.http import create_employee, link_user_to_employee, login
from tests.helpers.seed import cleanup, seed_tenant_company, seed_user


def test_ess_profile_requires_link() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="user-ess")

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.hr_core.router_ess"))
        token = login(client, email=user["email"], password=user["password"])["access_token"]

        me = client.get("/api/v1/ess/me/profile", headers={"Authorization": f"Bearer {token}"})
        assert me.status_code == 409, me.text
        body = me.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "ess.not_linked"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[user["user_id"]])


def test_ess_profile_after_link_and_safe_patch() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-ess")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="employee-ess")

    created_users = [admin["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.hr_core.router_ess"))

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        employee_code = f"ESS{uuid.uuid4().hex[:5].upper()}"
        employee_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=employee_code,
            first_name="ESS",
            last_name="User",
            email=employee_user["email"],
            join_date_value=date(2026, 1, 1),
        )
        link_user_to_employee(client, token=admin_token, employee_id=employee_id, user_id=employee_user["user_id"])

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]

        me = client.get("/api/v1/ess/me/profile", headers={"Authorization": f"Bearer {emp_token}"})
        assert me.status_code == 200, me.text
        assert me.json()["data"]["employee"]["employee_code"] == employee_code

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
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)
