from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text

from tests.helpers.app import make_app
from tests.helpers.http import create_employee, link_user_to_employee, login
from tests.helpers.seed import cleanup, seed_tenant_company, seed_user


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping API integration tests",
)


def test_mss_not_linked() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-mss")
    mgr = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="manager-mss")

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.hr_core.router_mss"))
        _ = login(client, email=admin["email"], password=admin["password"])  # sanity: auth works

        mgr_token = login(client, email=mgr["email"], password=mgr["password"])["access_token"]
        r = client.get("/api/v1/mss/team", headers={"Authorization": f"Bearer {mgr_token}"})
        assert r.status_code == 409, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "mss.not_linked"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"], mgr["user_id"]])


def test_mss_depth_direct_vs_indirect() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-mss")
    mgr = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="manager-mss")

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.hr_core.router_mss"))
        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        a_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code="A100",
            first_name="Manager",
            last_name="A",
        )
        link_user_to_employee(client, token=admin_token, employee_id=a_id, user_id=mgr["user_id"])

        b_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code="B100",
            first_name="Employee",
            last_name="B",
            manager_employee_id=a_id,
        )
        c_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code="C100",
            first_name="Employee",
            last_name="C",
            manager_employee_id=b_id,
        )

        mgr_token = login(client, email=mgr["email"], password=mgr["password"])["access_token"]

        direct = client.get(
            "/api/v1/mss/team",
            headers={"Authorization": f"Bearer {mgr_token}"},
            params={"depth": "1"},
        )
        assert direct.status_code == 200, direct.text
        items = direct.json()["data"]["items"]
        assert [i["employee_code"] for i in items] == ["B100"]
        assert items[0]["relationship_depth"] == 1

        all_ = client.get(
            "/api/v1/mss/team",
            headers={"Authorization": f"Bearer {mgr_token}"},
            params={"depth": "all"},
        )
        assert all_.status_code == 200, all_.text
        items_all = all_.json()["data"]["items"]
        assert [i["employee_code"] for i in items_all] == ["B100", "C100"]
        assert items_all[0]["relationship_depth"] == 1
        assert items_all[1]["relationship_depth"] == 2

        prof = client.get(f"/api/v1/mss/team/{c_id}", headers={"Authorization": f"Bearer {mgr_token}"})
        assert prof.status_code == 200, prof.text
        assert prof.json()["data"]["employee"]["employee_code"] == "C100"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"], mgr["user_id"]])


def test_mss_forbidden_employee_profile() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-mss")
    mgr = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="manager-mss")

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.hr_core.router_mss"))
        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        a_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code="A200",
            first_name="Manager",
            last_name="A",
        )
        link_user_to_employee(client, token=admin_token, employee_id=a_id, user_id=mgr["user_id"])

        _ = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code="B200",
            first_name="Employee",
            last_name="B",
            manager_employee_id=a_id,
        )
        outsider_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code="X200",
            first_name="Out",
            last_name="Side",
        )

        mgr_token = login(client, email=mgr["email"], password=mgr["password"])["access_token"]
        r = client.get(f"/api/v1/mss/team/{outsider_id}", headers={"Authorization": f"Bearer {mgr_token}"})
        assert r.status_code == 403, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "mss.forbidden_employee"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"], mgr["user_id"]])


def test_mss_filters_branch_and_org_unit() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine, with_second_branch=True)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-mss")
    mgr = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="manager-mss")

    ou1 = uuid.uuid4()
    ou2 = uuid.uuid4()

    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO tenancy.org_units (id, tenant_id, company_id, branch_id, parent_id, name, unit_type)
                    VALUES (:id, :tenant_id, :company_id, :branch_id, NULL, :name, 'DEPT')
                    """
                ),
                {
                    "id": ou1,
                    "tenant_id": tenant["tenant_id"],
                    "company_id": tenant["company_id"],
                    "branch_id": tenant["branch_id"],
                    "name": "Dept 1",
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO tenancy.org_units (id, tenant_id, company_id, branch_id, parent_id, name, unit_type)
                    VALUES (:id, :tenant_id, :company_id, :branch_id, NULL, :name, 'DEPT')
                    """
                ),
                {
                    "id": ou2,
                    "tenant_id": tenant["tenant_id"],
                    "company_id": tenant["company_id"],
                    "branch_id": tenant["branch2_id"],
                    "name": "Dept 2",
                },
            )

        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.hr_core.router_mss"))
        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        a_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code="A300",
            first_name="Manager",
            last_name="A",
        )
        link_user_to_employee(client, token=admin_token, employee_id=a_id, user_id=mgr["user_id"])

        _ = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code="B300",
            first_name="Employee",
            last_name="B",
            manager_employee_id=a_id,
            org_unit_id=str(ou1),
        )
        _ = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch2_id"],
            employee_code="C300",
            first_name="Employee",
            last_name="C",
            manager_employee_id=a_id,
            org_unit_id=str(ou2),
        )

        mgr_token = login(client, email=mgr["email"], password=mgr["password"])["access_token"]

        all_items = client.get("/api/v1/mss/team", headers={"Authorization": f"Bearer {mgr_token}"}).json()["data"]["items"]
        assert [i["employee_code"] for i in all_items] == ["B300", "C300"]

        b_only = client.get(
            "/api/v1/mss/team",
            headers={"Authorization": f"Bearer {mgr_token}"},
            params={"branch_id": tenant["branch_id"]},
        )
        assert b_only.status_code == 200, b_only.text
        assert [i["employee_code"] for i in b_only.json()["data"]["items"]] == ["B300"]

        c_only = client.get(
            "/api/v1/mss/team",
            headers={"Authorization": f"Bearer {mgr_token}"},
            params={"org_unit_id": str(ou2)},
        )
        assert c_only.status_code == 200, c_only.text
        assert [i["employee_code"] for i in c_only.json()["data"]["items"]] == ["C300"]
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"], mgr["user_id"]])


def test_mss_no_leak_across_company() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine, with_second_company=True)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-mss")
    mgr = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="manager-mss")

    outsider_employee_id = uuid.uuid4()
    outsider_person_id = uuid.uuid4()

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.hr_core.router_mss"))
        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        a_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code="A400",
            first_name="Manager",
            last_name="A",
        )
        link_user_to_employee(client, token=admin_token, employee_id=a_id, user_id=mgr["user_id"])

        _ = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code="B400",
            first_name="Employee",
            last_name="B",
            manager_employee_id=a_id,
        )

        # Insert an employee in company2 (not in subtree) via SQL.
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO hr_core.persons (id, tenant_id, first_name, last_name, address)
                    VALUES (:id, :tenant_id, 'Other', 'Company', '{}'::jsonb)
                    """
                ),
                {"id": outsider_person_id, "tenant_id": tenant["tenant_id"]},
            )
            conn.execute(
                text(
                    """
                    INSERT INTO hr_core.employees (id, tenant_id, company_id, person_id, employee_code, status)
                    VALUES (:id, :tenant_id, :company_id, :person_id, 'Z400', 'ACTIVE')
                    """
                ),
                {
                    "id": outsider_employee_id,
                    "tenant_id": tenant["tenant_id"],
                    "company_id": tenant["company2_id"],
                    "person_id": outsider_person_id,
                },
            )
            conn.execute(
                text(
                    """
                    INSERT INTO hr_core.employee_employment (
                      id, tenant_id, company_id, employee_id, branch_id, start_date, end_date, is_primary
                    ) VALUES (
                      :id, :tenant_id, :company_id, :employee_id, :branch_id, :start_date, NULL, true
                    )
                    """
                ),
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant["tenant_id"],
                    "company_id": tenant["company2_id"],
                    "employee_id": outsider_employee_id,
                    "branch_id": tenant["branch3_id"],
                    "start_date": date(2026, 1, 1),
                },
            )

        mgr_token = login(client, email=mgr["email"], password=mgr["password"])["access_token"]

        team = client.get("/api/v1/mss/team", headers={"Authorization": f"Bearer {mgr_token}"})
        assert team.status_code == 200, team.text
        codes = [i["employee_code"] for i in team.json()["data"]["items"]]
        assert "Z400" not in codes

        forbidden = client.get(f"/api/v1/mss/team/{outsider_employee_id}", headers={"Authorization": f"Bearer {mgr_token}"})
        assert forbidden.status_code == 403, forbidden.text
        assert forbidden.json()["error"]["code"] == "mss.forbidden_employee"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"], mgr["user_id"]])

