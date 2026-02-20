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


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_workflow_definition_leave_manager_only(client, *, token: str) -> None:
    # Make leave approvals deterministic for tests: single-step MANAGER approval.
    r = client.post(
        "/api/v1/workflow/definitions",
        headers=_auth(token),
        json={
            "request_type_code": "LEAVE_REQUEST",
            "code": f"LEAVE_REQUEST_V1_{uuid.uuid4().hex[:6]}",
            "name": "Leave Request (Manager only)",
            "version": 1,
        },
    )
    assert r.status_code == 200, r.text
    definition_id = r.json()["data"]["id"]

    r2 = client.post(
        f"/api/v1/workflow/definitions/{definition_id}/steps",
        headers=_auth(token),
        json={"steps": [{"step_index": 0, "assignee_type": "MANAGER"}]},
    )
    assert r2.status_code == 200, r2.text

    r3 = client.post(
        f"/api/v1/workflow/definitions/{definition_id}/activate",
        headers=_auth(token),
    )
    assert r3.status_code == 200, r3.text


def _setup_leave_basics(
    client,
    *,
    admin_token: str,
    tenant: dict[str, str],
    employee_id: str,
    leave_type_code: str = "ANNUAL",
    year_start_month: int = 1,
) -> dict[str, str]:
    # Weekly off is REQUIRED (Saudi weekend: Fri+Sat).
    put_weekly = client.put(
        f"/api/v1/leave/calendar/weekly-off?branch_id={tenant['branch_id']}",
        headers=_auth(admin_token),
        json={
            "days": [
                {"weekday": 0, "is_off": False},
                {"weekday": 1, "is_off": False},
                {"weekday": 2, "is_off": False},
                {"weekday": 3, "is_off": False},
                {"weekday": 4, "is_off": True},  # Fri
                {"weekday": 5, "is_off": True},  # Sat
                {"weekday": 6, "is_off": False},  # Sun
            ]
        },
    )
    assert put_weekly.status_code == 200, put_weekly.text

    # Leave type
    r_type = client.post(
        "/api/v1/leave/types",
        headers=_auth(admin_token),
        json={
            "code": leave_type_code,
            "name": "Annual Leave",
            "is_paid": True,
            "unit": "DAY",
            "requires_attachment": False,
            "allow_negative_balance": False,
            "is_active": True,
        },
    )
    assert r_type.status_code == 200, r_type.text

    # Leave policy
    r_pol = client.post(
        "/api/v1/leave/policies",
        headers=_auth(admin_token),
        json={
            "code": f"POL_{uuid.uuid4().hex[:6]}",
            "name": "Default Leave Policy",
            "company_id": tenant["company_id"],
            "branch_id": None,
            "effective_from": "2026-01-01",
            "effective_to": None,
            "year_start_month": year_start_month,
            "is_active": True,
        },
    )
    assert r_pol.status_code == 200, r_pol.text
    policy_id = r_pol.json()["data"]["id"]

    # Policy rules
    r_rules = client.post(
        f"/api/v1/leave/policies/{policy_id}/rules",
        headers=_auth(admin_token),
        json={"rules": [{"leave_type_code": leave_type_code, "annual_entitlement_days": 0, "allow_half_day": False}]},
    )
    assert r_rules.status_code == 200, r_rules.text

    # Assign policy to employee
    r_assign = client.post(
        f"/api/v1/leave/employees/{employee_id}/policy",
        headers=_auth(admin_token),
        json={"policy_id": policy_id, "effective_from": "2026-01-01", "effective_to": None},
    )
    assert r_assign.status_code == 200, r_assign.text

    return {"policy_id": str(policy_id), "leave_type_code": leave_type_code}


def _allocate(
    client,
    *,
    admin_token: str,
    employee_id: str,
    leave_type_code: str,
    year: int,
    days: float,
) -> str:
    r = client.post(
        "/api/v1/leave/allocations",
        headers=_auth(admin_token),
        json={"employee_id": employee_id, "leave_type_code": leave_type_code, "year": year, "days": days, "note": "seed"},
    )
    assert r.status_code == 200, r.text
    return r.json()["data"]["ledger_id"]


def test_leave_happy_path_manager_approves() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-leave")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-leave")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-leave")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.workflow.router",
                "app.domains.notifications.router",
                "app.domains.leave.router_ess",
                "app.domains.leave.router_hr",
                "app.domains.leave.router_mss",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        # Create manager employee + link
        manager_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="Manny",
            last_name="Manager",
        )
        link_user_to_employee(client, token=admin_token, employee_id=manager_emp_id, user_id=manager_user["user_id"])

        # Create employee with manager chain + link
        employee_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Eve",
            last_name="Employee",
            manager_employee_id=manager_emp_id,
        )
        link_user_to_employee(client, token=admin_token, employee_id=employee_emp_id, user_id=employee_user["user_id"])

        _create_workflow_definition_leave_manager_only(client, token=admin_token)

        basics = _setup_leave_basics(client, admin_token=admin_token, tenant=tenant, employee_id=employee_emp_id)
        _allocate(
            client,
            admin_token=admin_token,
            employee_id=employee_emp_id,
            leave_type_code=basics["leave_type_code"],
            year=2026,
            days=10,
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        submit = client.post(
            "/api/v1/leave/me/requests",
            headers=_auth(emp_token),
            json={
                "leave_type_code": basics["leave_type_code"],
                "start_date": "2026-02-02",
                "end_date": "2026-02-03",
                "unit": "DAY",
                "reason": "vacation",
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert submit.status_code == 200, submit.text
        leave_request_id = submit.json()["data"]["id"]
        workflow_request_id = submit.json()["data"]["workflow_request_id"]
        assert submit.json()["data"]["status"] == "PENDING"
        assert workflow_request_id is not None

        mgr_token = login(client, email=manager_user["email"], password=manager_user["password"])["access_token"]
        inbox = client.get("/api/v1/workflow/inbox?status=pending&limit=50", headers=_auth(mgr_token))
        assert inbox.status_code == 200, inbox.text
        assert any(i["id"] == workflow_request_id for i in inbox.json()["data"]["items"])

        # Manager approves (terminal in this definition) -> leave hook consumes ledger + writes attendance overrides.
        appr = client.post(
            f"/api/v1/workflow/requests/{workflow_request_id}/approve",
            headers=_auth(mgr_token),
            json={"comment": "approved"},
        )
        assert appr.status_code == 200, appr.text

        # Leave request status becomes APPROVED.
        mine = client.get("/api/v1/leave/me/requests?limit=50", headers=_auth(emp_token))
        assert mine.status_code == 200, mine.text
        row = next((r for r in mine.json()["data"]["items"] if r["id"] == leave_request_id), None)
        assert row is not None
        assert row["status"] == "APPROVED"

        # Ledger consumption row exists and is idempotent (unique by source).
        with engine.connect() as conn:
            used = conn.execute(
                text(
                    """
                    SELECT delta_days
                    FROM leave.leave_ledger
                    WHERE tenant_id = :tenant_id
                      AND source_type = 'LEAVE_REQUEST'
                      AND source_id = :source_id
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "source_id": leave_request_id},
            ).scalar()
            assert used is not None
            assert float(used) == -2.0

            overrides = int(
                conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM attendance.day_overrides
                        WHERE tenant_id = :tenant_id
                          AND source_type = 'LEAVE_REQUEST'
                          AND source_id = :source_id
                        """
                    ),
                    {"tenant_id": tenant["tenant_id"], "source_id": leave_request_id},
                ).scalar()
                or 0
            )
            assert overrides == 2

        # Notifications: finalized notification for requester.
        from app.worker.notification_worker import consume_once

        consume_once(limit=50)
        emp_notifs = client.get("/api/v1/notifications?unread_only=1&limit=50", headers=_auth(emp_token))
        assert emp_notifs.status_code == 200, emp_notifs.text
        assert any(n["type"] == "workflow.request.finalized" and n["entity_id"] == workflow_request_id for n in emp_notifs.json()["data"]["items"])

        # Team calendar shows the approved span.
        cal = client.get(
            "/api/v1/leave/team/calendar?from=2026-02-01&to=2026-02-28&depth=1",
            headers=_auth(mgr_token),
        )
        assert cal.status_code == 200, cal.text
        assert any(i["leave_request_id"] == leave_request_id for i in cal.json()["data"]["items"])

        # Audit rows exist for leave finalize + consume.
        with engine.connect() as conn:
            cnt = int(
                conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM audit.audit_log
                        WHERE tenant_id = :tenant_id
                          AND action in ('leave.ledger.consume','leave.request.finalize')
                          AND entity_id = :entity_id
                        """
                    ),
                    {"tenant_id": tenant["tenant_id"], "entity_id": leave_request_id},
                ).scalar()
                or 0
            )
            assert cnt >= 1
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_leave_overlap_rejected() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-ov")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-ov")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-ov")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.leave.router_ess", "app.domains.leave.router_hr"))

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        manager_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="M",
            last_name="G",
        )
        link_user_to_employee(client, token=admin_token, employee_id=manager_emp_id, user_id=manager_user["user_id"])

        employee_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="E",
            last_name="E",
            manager_employee_id=manager_emp_id,
        )
        link_user_to_employee(client, token=admin_token, employee_id=employee_emp_id, user_id=employee_user["user_id"])

        _create_workflow_definition_leave_manager_only(client, token=admin_token)
        basics = _setup_leave_basics(client, admin_token=admin_token, tenant=tenant, employee_id=employee_emp_id)
        _allocate(client, admin_token=admin_token, employee_id=employee_emp_id, leave_type_code=basics["leave_type_code"], year=2026, days=10)

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]

        # First request (pending)
        r1 = client.post(
            "/api/v1/leave/me/requests",
            headers=_auth(emp_token),
            json={"leave_type_code": basics["leave_type_code"], "start_date": "2026-02-10", "end_date": "2026-02-10", "unit": "DAY"},
        )
        assert r1.status_code == 200, r1.text

        # Overlapping request (same day)
        r2 = client.post(
            "/api/v1/leave/me/requests",
            headers=_auth(emp_token),
            json={"leave_type_code": basics["leave_type_code"], "start_date": "2026-02-10", "end_date": "2026-02-10", "unit": "DAY"},
        )
        assert r2.status_code == 409, r2.text
        assert r2.json()["error"]["code"] == "leave.overlap"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_leave_insufficient_balance() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-bal")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-bal")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-bal")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.leave.router_ess", "app.domains.leave.router_hr"))

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        manager_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="M",
            last_name="G",
        )
        link_user_to_employee(client, token=admin_token, employee_id=manager_emp_id, user_id=manager_user["user_id"])

        employee_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="E",
            last_name="E",
            manager_employee_id=manager_emp_id,
        )
        link_user_to_employee(client, token=admin_token, employee_id=employee_emp_id, user_id=employee_user["user_id"])

        _create_workflow_definition_leave_manager_only(client, token=admin_token)
        basics = _setup_leave_basics(client, admin_token=admin_token, tenant=tenant, employee_id=employee_emp_id)
        _allocate(client, admin_token=admin_token, employee_id=employee_emp_id, leave_type_code=basics["leave_type_code"], year=2026, days=1)

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        r = client.post(
            "/api/v1/leave/me/requests",
            headers=_auth(emp_token),
            json={"leave_type_code": basics["leave_type_code"], "start_date": "2026-02-02", "end_date": "2026-02-03", "unit": "DAY"},
        )
        assert r.status_code == 409, r.text
        assert r.json()["error"]["code"] == "leave.insufficient_balance"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_leave_weekend_holiday_excluded() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-cal")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-cal")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-cal")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.leave.router_ess", "app.domains.leave.router_hr"))

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        manager_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="M",
            last_name="G",
        )
        link_user_to_employee(client, token=admin_token, employee_id=manager_emp_id, user_id=manager_user["user_id"])

        employee_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="E",
            last_name="E",
            manager_employee_id=manager_emp_id,
        )
        link_user_to_employee(client, token=admin_token, employee_id=employee_emp_id, user_id=employee_user["user_id"])

        _create_workflow_definition_leave_manager_only(client, token=admin_token)
        basics = _setup_leave_basics(client, admin_token=admin_token, tenant=tenant, employee_id=employee_emp_id)
        _allocate(client, admin_token=admin_token, employee_id=employee_emp_id, leave_type_code=basics["leave_type_code"], year=2026, days=10)

        # Add a branch holiday on 2026-02-08 (Sun).
        h = client.post(
            "/api/v1/leave/calendar/holidays",
            headers=_auth(admin_token),
            json={"day": "2026-02-08", "name": "Founding Day", "branch_id": tenant["branch_id"]},
        )
        assert h.status_code == 200, h.text

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        r = client.post(
            "/api/v1/leave/me/requests",
            headers=_auth(emp_token),
            json={"leave_type_code": basics["leave_type_code"], "start_date": "2026-02-05", "end_date": "2026-02-08", "unit": "DAY"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["data"]["requested_days"] == 1.0
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_leave_tenant_isolation() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant_a = seed_tenant_company(engine)
    tenant_b = seed_tenant_company(engine)

    admin_a = seed_user(engine, tenant_id=tenant_a["tenant_id"], company_id=tenant_a["company_id"], branch_id=tenant_a["branch_id"], role_code="ADMIN", email_prefix="admin-la")
    manager_a = seed_user(engine, tenant_id=tenant_a["tenant_id"], company_id=tenant_a["company_id"], branch_id=tenant_a["branch_id"], role_code="MANAGER", email_prefix="mgr-la")
    employee_a = seed_user(engine, tenant_id=tenant_a["tenant_id"], company_id=tenant_a["company_id"], branch_id=tenant_a["branch_id"], role_code="EMPLOYEE", email_prefix="emp-la")

    admin_b = seed_user(engine, tenant_id=tenant_b["tenant_id"], company_id=tenant_b["company_id"], branch_id=tenant_b["branch_id"], role_code="ADMIN", email_prefix="admin-lb")
    manager_b = seed_user(engine, tenant_id=tenant_b["tenant_id"], company_id=tenant_b["company_id"], branch_id=tenant_b["branch_id"], role_code="MANAGER", email_prefix="mgr-lb")
    employee_b = seed_user(engine, tenant_id=tenant_b["tenant_id"], company_id=tenant_b["company_id"], branch_id=tenant_b["branch_id"], role_code="EMPLOYEE", email_prefix="emp-lb")

    created_users = [admin_a["user_id"], manager_a["user_id"], employee_a["user_id"], admin_b["user_id"], manager_b["user_id"], employee_b["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.leave.router_ess", "app.domains.leave.router_hr"))

        # Setup tenant B leave request
        token_b = login(client, email=admin_b["email"], password=admin_b["password"])["access_token"]

        mgr_emp_b = create_employee(
            client,
            token=token_b,
            company_id=tenant_b["company_id"],
            branch_id=tenant_b["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="B",
            last_name="Mgr",
        )
        link_user_to_employee(client, token=token_b, employee_id=mgr_emp_b, user_id=manager_b["user_id"])

        emp_emp_b = create_employee(
            client,
            token=token_b,
            company_id=tenant_b["company_id"],
            branch_id=tenant_b["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="B",
            last_name="Emp",
            manager_employee_id=mgr_emp_b,
        )
        link_user_to_employee(client, token=token_b, employee_id=emp_emp_b, user_id=employee_b["user_id"])

        _create_workflow_definition_leave_manager_only(client, token=token_b)
        basics_b = _setup_leave_basics(client, admin_token=token_b, tenant=tenant_b, employee_id=emp_emp_b)
        _allocate(client, admin_token=token_b, employee_id=emp_emp_b, leave_type_code=basics_b["leave_type_code"], year=2026, days=10)

        emp_token_b = login(client, email=employee_b["email"], password=employee_b["password"])["access_token"]
        submit_b = client.post(
            "/api/v1/leave/me/requests",
            headers=_auth(emp_token_b),
            json={"leave_type_code": basics_b["leave_type_code"], "start_date": "2026-02-02", "end_date": "2026-02-02", "unit": "DAY"},
        )
        assert submit_b.status_code == 200, submit_b.text
        leave_request_b = submit_b.json()["data"]["id"]

        # Tenant A employee tries to cancel tenant B request -> 404 (not found in tenant A scope).
        token_a = login(client, email=admin_a["email"], password=admin_a["password"])["access_token"]
        mgr_emp_a = create_employee(
            client,
            token=token_a,
            company_id=tenant_a["company_id"],
            branch_id=tenant_a["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="A",
            last_name="Mgr",
        )
        link_user_to_employee(client, token=token_a, employee_id=mgr_emp_a, user_id=manager_a["user_id"])

        emp_emp_a = create_employee(
            client,
            token=token_a,
            company_id=tenant_a["company_id"],
            branch_id=tenant_a["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="A",
            last_name="Emp",
            manager_employee_id=mgr_emp_a,
        )
        link_user_to_employee(client, token=token_a, employee_id=emp_emp_a, user_id=employee_a["user_id"])

        basics_a = _setup_leave_basics(client, admin_token=token_a, tenant=tenant_a, employee_id=emp_emp_a)
        _allocate(client, admin_token=token_a, employee_id=emp_emp_a, leave_type_code=basics_a["leave_type_code"], year=2026, days=10)

        emp_token_a = login(client, email=employee_a["email"], password=employee_a["password"])["access_token"]
        cancel_other = client.post(
            f"/api/v1/leave/me/requests/{leave_request_b}/cancel",
            headers=_auth(emp_token_a),
        )
        assert cancel_other.status_code == 404, cancel_other.text
    finally:
        cleanup(engine, tenant_id=tenant_a["tenant_id"], user_ids=[admin_a["user_id"], manager_a["user_id"], employee_a["user_id"]])
        cleanup(engine, tenant_id=tenant_b["tenant_id"], user_ids=[admin_b["user_id"], manager_b["user_id"], employee_b["user_id"]])


def test_leave_idempotent_create() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-idem")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-idem")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-idem")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.leave.router_ess", "app.domains.leave.router_hr"))

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        manager_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="M",
            last_name="G",
        )
        link_user_to_employee(client, token=admin_token, employee_id=manager_emp_id, user_id=manager_user["user_id"])

        employee_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="E",
            last_name="E",
            manager_employee_id=manager_emp_id,
        )
        link_user_to_employee(client, token=admin_token, employee_id=employee_emp_id, user_id=employee_user["user_id"])

        _create_workflow_definition_leave_manager_only(client, token=admin_token)
        basics = _setup_leave_basics(client, admin_token=admin_token, tenant=tenant, employee_id=employee_emp_id)
        _allocate(client, admin_token=admin_token, employee_id=employee_emp_id, leave_type_code=basics["leave_type_code"], year=2026, days=10)

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]

        idem = f"idem-{uuid.uuid4().hex}"
        r1 = client.post(
            "/api/v1/leave/me/requests",
            headers=_auth(emp_token),
            json={"leave_type_code": basics["leave_type_code"], "start_date": "2026-02-23", "end_date": "2026-02-23", "unit": "DAY", "idempotency_key": idem},
        )
        assert r1.status_code == 200, r1.text
        first_id = r1.json()["data"]["id"]

        r2 = client.post(
            "/api/v1/leave/me/requests",
            headers=_auth(emp_token),
            json={"leave_type_code": basics["leave_type_code"], "start_date": "2026-02-23", "end_date": "2026-02-23", "unit": "DAY", "idempotency_key": idem},
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["data"]["id"] == first_id

        # Different payload with same idempotency_key -> 409
        r3 = client.post(
            "/api/v1/leave/me/requests",
            headers=_auth(emp_token),
            json={"leave_type_code": basics["leave_type_code"], "start_date": "2026-02-24", "end_date": "2026-02-24", "unit": "DAY", "idempotency_key": idem},
        )
        assert r3.status_code == 409, r3.text
        assert r3.json()["error"]["code"] == "leave.idempotency.conflict"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_leave_cancel_pending() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-can")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-can")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-can")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.leave.router_ess", "app.domains.leave.router_hr"))

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        manager_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="M",
            last_name="G",
        )
        link_user_to_employee(client, token=admin_token, employee_id=manager_emp_id, user_id=manager_user["user_id"])

        employee_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="E",
            last_name="E",
            manager_employee_id=manager_emp_id,
        )
        link_user_to_employee(client, token=admin_token, employee_id=employee_emp_id, user_id=employee_user["user_id"])

        _create_workflow_definition_leave_manager_only(client, token=admin_token)
        basics = _setup_leave_basics(client, admin_token=admin_token, tenant=tenant, employee_id=employee_emp_id)
        _allocate(client, admin_token=admin_token, employee_id=employee_emp_id, leave_type_code=basics["leave_type_code"], year=2026, days=10)

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]

        r = client.post(
            "/api/v1/leave/me/requests",
            headers=_auth(emp_token),
            json={"leave_type_code": basics["leave_type_code"], "start_date": "2026-02-24", "end_date": "2026-02-24", "unit": "DAY"},
        )
        assert r.status_code == 200, r.text
        leave_request_id = r.json()["data"]["id"]

        c = client.post(f"/api/v1/leave/me/requests/{leave_request_id}/cancel", headers=_auth(emp_token))
        assert c.status_code == 200, c.text
        assert c.json()["data"]["status"] == "CANCELED"

        # No consumption ledger rows on cancel.
        with engine.connect() as conn:
            cnt = int(
                conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM leave.leave_ledger
                        WHERE tenant_id = :tenant_id
                          AND source_type = 'LEAVE_REQUEST'
                          AND source_id = :source_id
                        """
                    ),
                    {"tenant_id": tenant["tenant_id"], "source_id": leave_request_id},
                ).scalar()
                or 0
            )
            assert cnt == 0
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_leave_participant_only_access() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-p")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-p")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-p")
    outsider_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="outsider-p")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"], outsider_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.leave.router_ess", "app.domains.leave.router_hr"))

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        manager_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="M",
            last_name="G",
        )
        link_user_to_employee(client, token=admin_token, employee_id=manager_emp_id, user_id=manager_user["user_id"])

        employee_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="E",
            last_name="E",
            manager_employee_id=manager_emp_id,
        )
        link_user_to_employee(client, token=admin_token, employee_id=employee_emp_id, user_id=employee_user["user_id"])

        outsider_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"O{uuid.uuid4().hex[:6].upper()}",
            first_name="O",
            last_name="O",
        )
        link_user_to_employee(client, token=admin_token, employee_id=outsider_emp_id, user_id=outsider_user["user_id"])

        _create_workflow_definition_leave_manager_only(client, token=admin_token)
        basics = _setup_leave_basics(client, admin_token=admin_token, tenant=tenant, employee_id=employee_emp_id)
        _allocate(client, admin_token=admin_token, employee_id=employee_emp_id, leave_type_code=basics["leave_type_code"], year=2026, days=10)

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]

        r = client.post(
            "/api/v1/leave/me/requests",
            headers=_auth(emp_token),
            json={"leave_type_code": basics["leave_type_code"], "start_date": "2026-02-26", "end_date": "2026-02-26", "unit": "DAY"},
        )
        assert r.status_code == 200, r.text
        leave_request_id = r.json()["data"]["id"]

        outsider_token = login(client, email=outsider_user["email"], password=outsider_user["password"])["access_token"]
        deny = client.post(f"/api/v1/leave/me/requests/{leave_request_id}/cancel", headers=_auth(outsider_token))
        assert deny.status_code == 404, deny.text
        assert deny.json()["error"]["code"] == "leave.request.not_found"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)
