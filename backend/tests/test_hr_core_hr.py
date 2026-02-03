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
from tests.helpers.http import create_employee, login
from tests.helpers.seed import cleanup, seed_tenant_company, seed_user


def test_hr_create_employee_and_directory() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-hrcore",
    )
    created_users = [admin["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.hr_core.router_ess"))
        token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        employee_code = f"E{uuid.uuid4().hex[:6].upper()}"
        employee_id = create_employee(
            client,
            token=token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=employee_code,
            first_name="Alice",
            last_name="One",
            email="alice.one@example.com",
            join_date_value=date(2026, 1, 1),
        )

        directory = client.get(
            "/api/v1/hr/employees",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": employee_code},
        )
        assert directory.status_code == 200, directory.text
        items = directory.json()["data"]["items"]
        assert any(r["employee_id"] == employee_id for r in items)

        details = client.get(
            f"/api/v1/hr/employees/{employee_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert details.status_code == 200, details.text
        assert details.json()["data"]["employee"]["employee_code"] == employee_code
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_hr_employment_change_and_cycle_prevention() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-hrcore",
    )
    created_users = [admin["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.hr_core.router_ess"))
        token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        a_id = create_employee(
            client,
            token=token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"A{uuid.uuid4().hex[:6].upper()}",
            first_name="Manager",
            last_name="A",
        )
        b_id = create_employee(
            client,
            token=token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"B{uuid.uuid4().hex[:6].upper()}",
            first_name="Employee",
            last_name="B",
            manager_employee_id=a_id,
        )

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
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)
