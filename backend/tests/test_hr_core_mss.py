from __future__ import annotations

import os
import uuid
from datetime import date

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
    from app.domains.hr_core.router_hr import router as hr_router
    from app.domains.hr_core.router_mss import router as mss_router

    app = FastAPI()
    app.add_middleware(TraceIdMiddleware)
    install_exception_handlers(app)
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(hr_router, prefix="/api/v1")
    app.include_router(mss_router, prefix="/api/v1")
    return app


def _require_vnext(conn) -> None:
    for fqtn in (
        "tenancy.tenants",
        "tenancy.companies",
        "tenancy.branches",
        "tenancy.org_units",
        "iam.users",
        "iam.roles",
        "iam.user_roles",
        "hr_core.persons",
        "hr_core.employees",
        "hr_core.employee_employment",
        "hr_core.employee_user_links",
    ):
        exists = conn.execute(text("SELECT to_regclass(:fqtn)"), {"fqtn": fqtn}).scalar()
        assert exists is not None, f"Missing required table {fqtn}; did you run migrations?"


def _role_id(conn, code: str) -> uuid.UUID:
    rid = conn.execute(text("SELECT id FROM iam.roles WHERE code = :code"), {"code": code}).scalar()
    assert rid is not None, f"Missing IAM role {code}; ensure seed migrations ran."
    return rid


def _seed_tenant_company(engine, *, with_second_branch: bool = False, with_second_company: bool = False) -> dict[str, str]:
    tenant_id = uuid.uuid4()
    company1_id = uuid.uuid4()
    branch1_id = uuid.uuid4()

    company2_id = uuid.uuid4() if with_second_company else None
    branch2_id = uuid.uuid4() if with_second_branch else None
    branch3_id = uuid.uuid4() if with_second_company else None

    with engine.begin() as conn:
        _require_vnext(conn)

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
                "id": company1_id,
                "tenant_id": tenant_id,
                "name": f"Company {company1_id.hex[:6]}",
                "legal_name": f"Company {company1_id.hex[:6]} LLC",
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
                "id": branch1_id,
                "tenant_id": tenant_id,
                "company_id": company1_id,
                "name": "HQ",
                "code": f"HQ{branch1_id.hex[:4].upper()}",
            },
        )

        if branch2_id is not None:
            conn.execute(
                text(
                    """
                    INSERT INTO tenancy.branches (id, tenant_id, company_id, name, code, timezone, address, status)
                    VALUES (:id, :tenant_id, :company_id, :name, :code, 'Asia/Riyadh', '{}'::jsonb, 'ACTIVE')
                    """
                ),
                {
                    "id": branch2_id,
                    "tenant_id": tenant_id,
                    "company_id": company1_id,
                    "name": "Branch 2",
                    "code": f"B2{branch2_id.hex[:4].upper()}",
                },
            )

        if company2_id is not None and branch3_id is not None:
            conn.execute(
                text(
                    """
                    INSERT INTO tenancy.companies (id, tenant_id, name, legal_name, currency_code, timezone, status)
                    VALUES (:id, :tenant_id, :name, :legal_name, 'SAR', 'Asia/Riyadh', 'ACTIVE')
                    """
                ),
                {
                    "id": company2_id,
                    "tenant_id": tenant_id,
                    "name": f"Company2 {company2_id.hex[:6]}",
                    "legal_name": f"Company2 {company2_id.hex[:6]} LLC",
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
                    "id": branch3_id,
                    "tenant_id": tenant_id,
                    "company_id": company2_id,
                    "name": "C2-HQ",
                    "code": f"C2{branch3_id.hex[:4].upper()}",
                },
            )

    out = {"tenant_id": str(tenant_id), "company1_id": str(company1_id), "branch1_id": str(branch1_id)}
    if branch2_id is not None:
        out["branch2_id"] = str(branch2_id)
    if company2_id is not None and branch3_id is not None:
        out["company2_id"] = str(company2_id)
        out["branch3_id"] = str(branch3_id)
    return out


def _seed_user(engine, *, tenant_id: str, company_id: str, branch_id: str, role_code: str) -> dict[str, str]:
    user_id = uuid.uuid4()
    email = f"{role_code.lower()}-mss+{user_id.hex[:10]}@example.com"
    password = "StrongPass123"

    from app.auth.passwords import hash_password

    with engine.begin() as conn:
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
                "role_id": _role_id(conn, role_code),
            },
        )

    return {"user_id": str(user_id), "email": email, "password": password}


def _cleanup(engine, *, tenant_id: str, user_ids: list[str]) -> None:
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM tenancy.tenants WHERE id = :id"), {"id": tenant_id})
    if user_ids:
        with engine.begin() as conn:
            for uid in user_ids:
                conn.execute(text("DELETE FROM iam.users WHERE id = :id"), {"id": uid})


def _login(client, *, email: str, password: str) -> str:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["data"]["access_token"]


def _create_employee(
    client,
    *,
    token: str,
    company_id: str,
    branch_id: str,
    employee_code: str,
    first_name: str,
    last_name: str,
    manager_employee_id: str | None = None,
    org_unit_id: str | None = None,
) -> str:
    payload: dict[str, object] = {
        "person": {"first_name": first_name, "last_name": last_name, "address": {}},
        "employee": {"company_id": company_id, "employee_code": employee_code, "status": "ACTIVE"},
        "employment": {"start_date": str(date(2026, 1, 1)), "branch_id": branch_id, "is_primary": True},
    }
    if manager_employee_id is not None:
        payload["employment"]["manager_employee_id"] = manager_employee_id  # type: ignore[index]
    if org_unit_id is not None:
        payload["employment"]["org_unit_id"] = org_unit_id  # type: ignore[index]

    r = client.post("/api/v1/hr/employees", headers={"Authorization": f"Bearer {token}"}, json=payload)
    assert r.status_code == 200, r.text
    return r.json()["data"]["employee"]["id"]


def _link_user(client, *, token: str, employee_id: str, user_id: str) -> None:
    r = client.post(
        f"/api/v1/hr/employees/{employee_id}/link-user",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": user_id},
    )
    assert r.status_code == 200, r.text


def test_mss_not_linked() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = _seed_tenant_company(engine)
    admin = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company1_id"], branch_id=tenant["branch1_id"], role_code="ADMIN")
    mgr = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company1_id"], branch_id=tenant["branch1_id"], role_code="MANAGER")

    try:
        from fastapi.testclient import TestClient

        client = TestClient(_make_app())
        _ = _login(client, email=admin["email"], password=admin["password"])  # ensures auth stack works

        mgr_token = _login(client, email=mgr["email"], password=mgr["password"])
        r = client.get("/api/v1/mss/team", headers={"Authorization": f"Bearer {mgr_token}"})
        assert r.status_code == 409, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "mss.not_linked"
    finally:
        _cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"], mgr["user_id"]])


def test_mss_depth_direct_vs_indirect() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = _seed_tenant_company(engine)
    admin = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company1_id"], branch_id=tenant["branch1_id"], role_code="ADMIN")
    mgr = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company1_id"], branch_id=tenant["branch1_id"], role_code="MANAGER")

    try:
        from fastapi.testclient import TestClient

        client = TestClient(_make_app())
        admin_token = _login(client, email=admin["email"], password=admin["password"])

        a_id = _create_employee(
            client,
            token=admin_token,
            company_id=tenant["company1_id"],
            branch_id=tenant["branch1_id"],
            employee_code="A100",
            first_name="Manager",
            last_name="A",
        )
        _link_user(client, token=admin_token, employee_id=a_id, user_id=mgr["user_id"])

        b_id = _create_employee(
            client,
            token=admin_token,
            company_id=tenant["company1_id"],
            branch_id=tenant["branch1_id"],
            employee_code="B100",
            first_name="Employee",
            last_name="B",
            manager_employee_id=a_id,
        )
        c_id = _create_employee(
            client,
            token=admin_token,
            company_id=tenant["company1_id"],
            branch_id=tenant["branch1_id"],
            employee_code="C100",
            first_name="Employee",
            last_name="C",
            manager_employee_id=b_id,
        )

        mgr_token = _login(client, email=mgr["email"], password=mgr["password"])

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

        # Sanity: manager can view team member profile for direct/indirect.
        prof = client.get(f"/api/v1/mss/team/{c_id}", headers={"Authorization": f"Bearer {mgr_token}"})
        assert prof.status_code == 200, prof.text
        assert prof.json()["data"]["employee"]["employee_code"] == "C100"
    finally:
        _cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"], mgr["user_id"]])


def test_mss_forbidden_employee_profile() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = _seed_tenant_company(engine)
    admin = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company1_id"], branch_id=tenant["branch1_id"], role_code="ADMIN")
    mgr = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company1_id"], branch_id=tenant["branch1_id"], role_code="MANAGER")

    try:
        from fastapi.testclient import TestClient

        client = TestClient(_make_app())
        admin_token = _login(client, email=admin["email"], password=admin["password"])

        a_id = _create_employee(
            client,
            token=admin_token,
            company_id=tenant["company1_id"],
            branch_id=tenant["branch1_id"],
            employee_code="A200",
            first_name="Manager",
            last_name="A",
        )
        _link_user(client, token=admin_token, employee_id=a_id, user_id=mgr["user_id"])

        _ = _create_employee(
            client,
            token=admin_token,
            company_id=tenant["company1_id"],
            branch_id=tenant["branch1_id"],
            employee_code="B200",
            first_name="Employee",
            last_name="B",
            manager_employee_id=a_id,
        )
        outsider_id = _create_employee(
            client,
            token=admin_token,
            company_id=tenant["company1_id"],
            branch_id=tenant["branch1_id"],
            employee_code="X200",
            first_name="Out",
            last_name="Side",
        )

        mgr_token = _login(client, email=mgr["email"], password=mgr["password"])
        r = client.get(f"/api/v1/mss/team/{outsider_id}", headers={"Authorization": f"Bearer {mgr_token}"})
        assert r.status_code == 403, r.text
        body = r.json()
        assert body["ok"] is False
        assert body["error"]["code"] == "mss.forbidden_employee"
    finally:
        _cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"], mgr["user_id"]])


def test_mss_filters_branch_and_org_unit() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = _seed_tenant_company(engine, with_second_branch=True)
    admin = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company1_id"], branch_id=tenant["branch1_id"], role_code="ADMIN")
    mgr = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company1_id"], branch_id=tenant["branch1_id"], role_code="MANAGER")

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
                    "company_id": tenant["company1_id"],
                    "branch_id": tenant["branch1_id"],
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
                    "company_id": tenant["company1_id"],
                    "branch_id": tenant["branch2_id"],
                    "name": "Dept 2",
                },
            )

        from fastapi.testclient import TestClient

        client = TestClient(_make_app())
        admin_token = _login(client, email=admin["email"], password=admin["password"])

        a_id = _create_employee(
            client,
            token=admin_token,
            company_id=tenant["company1_id"],
            branch_id=tenant["branch1_id"],
            employee_code="A300",
            first_name="Manager",
            last_name="A",
        )
        _link_user(client, token=admin_token, employee_id=a_id, user_id=mgr["user_id"])

        _ = _create_employee(
            client,
            token=admin_token,
            company_id=tenant["company1_id"],
            branch_id=tenant["branch1_id"],
            employee_code="B300",
            first_name="Employee",
            last_name="B",
            manager_employee_id=a_id,
            org_unit_id=str(ou1),
        )
        _ = _create_employee(
            client,
            token=admin_token,
            company_id=tenant["company1_id"],
            branch_id=tenant["branch2_id"],
            employee_code="C300",
            first_name="Employee",
            last_name="C",
            manager_employee_id=a_id,
            org_unit_id=str(ou2),
        )

        mgr_token = _login(client, email=mgr["email"], password=mgr["password"])

        all_items = client.get("/api/v1/mss/team", headers={"Authorization": f"Bearer {mgr_token}"}).json()["data"]["items"]
        assert [i["employee_code"] for i in all_items] == ["B300", "C300"]

        b_only = client.get(
            "/api/v1/mss/team",
            headers={"Authorization": f"Bearer {mgr_token}"},
            params={"branch_id": tenant["branch1_id"]},
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
        _cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"], mgr["user_id"]])


def test_mss_no_leak_across_company() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = _seed_tenant_company(engine, with_second_company=True)
    admin = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company1_id"], branch_id=tenant["branch1_id"], role_code="ADMIN")
    mgr = _seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company1_id"], branch_id=tenant["branch1_id"], role_code="MANAGER")

    outsider_employee_id = uuid.uuid4()
    outsider_person_id = uuid.uuid4()

    try:
        from fastapi.testclient import TestClient

        client = TestClient(_make_app())
        admin_token = _login(client, email=admin["email"], password=admin["password"])

        a_id = _create_employee(
            client,
            token=admin_token,
            company_id=tenant["company1_id"],
            branch_id=tenant["branch1_id"],
            employee_code="A400",
            first_name="Manager",
            last_name="A",
        )
        _link_user(client, token=admin_token, employee_id=a_id, user_id=mgr["user_id"])

        _ = _create_employee(
            client,
            token=admin_token,
            company_id=tenant["company1_id"],
            branch_id=tenant["branch1_id"],
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

        mgr_token = _login(client, email=mgr["email"], password=mgr["password"])

        team = client.get("/api/v1/mss/team", headers={"Authorization": f"Bearer {mgr_token}"})
        assert team.status_code == 200, team.text
        codes = [i["employee_code"] for i in team.json()["data"]["items"]]
        assert "Z400" not in codes

        forbidden = client.get(f"/api/v1/mss/team/{outsider_employee_id}", headers={"Authorization": f"Bearer {mgr_token}"})
        assert forbidden.status_code == 403, forbidden.text
        assert forbidden.json()["error"]["code"] == "mss.forbidden_employee"
    finally:
        _cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"], mgr["user_id"]])

