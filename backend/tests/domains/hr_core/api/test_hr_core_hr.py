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
                "branch_id": tenant["branch_id"],
                "manager_employee_id": b_id,
            },
        )
        assert change.status_code == 400, change.text
        body = change.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "hr.manager.cycle"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_hr_employee_link_user_is_reflected_in_employee_detail_and_directory() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-hrcore-link",
    )
    employee_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="employee-hrcore-link",
    )
    other_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="employee-hrcore-link-2",
    )

    created_users = [admin["user_id"], employee_user["user_id"], other_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr"))
        token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        employee_code = f"E{uuid.uuid4().hex[:6].upper()}"
        employee_id = create_employee(
            client,
            token=token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=employee_code,
            first_name="Link",
            last_name="Target",
        )

        # Before linking, detail should show linked_user = null (or omit it).
        before = client.get(
            f"/api/v1/hr/employees/{employee_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert before.status_code == 200, before.text
        assert before.json()["data"].get("linked_user") is None

        # Link user and ensure the link is reflected in subsequent reads.
        link_user_to_employee(
            client,
            token=token,
            employee_id=employee_id,
            user_id=employee_user["user_id"],
        )

        after = client.get(
            f"/api/v1/hr/employees/{employee_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert after.status_code == 200, after.text
        linked = after.json()["data"]["linked_user"]
        assert linked is not None
        assert linked["user_id"] == employee_user["user_id"]
        assert linked["email"] == employee_user["email"]
        assert linked["status"] == "ACTIVE"
        assert linked["linked_at"]

        # Directory includes a cheap "has_user_link" flag.
        directory = client.get(
            "/api/v1/hr/employees",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": employee_code},
        )
        assert directory.status_code == 200, directory.text
        row = next(r for r in directory.json()["data"]["items"] if r["employee_id"] == employee_id)
        assert row["has_user_link"] is True

        # Idempotent: linking the same user twice is safe.
        idempotent = client.post(
            f"/api/v1/hr/employees/{employee_id}/link-user",
            headers={"Authorization": f"Bearer {token}"},
            json={"user_id": employee_user["user_id"]},
        )
        assert idempotent.status_code == 200, idempotent.text

        # Conflict: linking a different user to an already-linked employee is rejected.
        conflict = client.post(
            f"/api/v1/hr/employees/{employee_id}/link-user",
            headers={"Authorization": f"Bearer {token}"},
            json={"user_id": other_user["user_id"]},
        )
        assert conflict.status_code == 409, conflict.text
        assert conflict.json()["ok"] is False
        assert conflict.json()["error"]["code"] == "hr.employee_user_link.conflict"

        # User-in-use: the same user cannot be linked to multiple employees.
        other_employee_id = create_employee(
            client,
            token=token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Other",
            last_name="Employee",
        )
        user_in_use = client.post(
            f"/api/v1/hr/employees/{other_employee_id}/link-user",
            headers={"Authorization": f"Bearer {token}"},
            json={"user_id": employee_user["user_id"]},
        )
        assert user_in_use.status_code == 409, user_in_use.text
        assert user_in_use.json()["ok"] is False
        assert user_in_use.json()["error"]["code"] == "hr.employee_user_link.user_in_use"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)
