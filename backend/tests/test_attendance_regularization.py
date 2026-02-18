from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

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


def _create_workflow_definition_attendance_correction_manager_only(client, *, token: str) -> None:
    r = client.post(
        "/api/v1/workflow/definitions",
        headers=_auth(token),
        json={
            "request_type_code": "ATTENDANCE_CORRECTION",
            "code": f"ATT_CORR_V1_{uuid.uuid4().hex[:6]}",
            "name": "Attendance Correction (Manager only)",
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


def test_attendance_correction_happy_path_manager_approves() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-att")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-att")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-att")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.workflow.router",
                "app.domains.notifications.router",
                "app.domains.attendance.router_ess",
                "app.domains.attendance.router_admin",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        # Manager employee + link
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

        # Employee with manager chain + link
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

        _create_workflow_definition_attendance_correction_manager_only(client, token=admin_token)

        day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        submit = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token),
            json={
                "day": day,
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "PRESENT_OVERRIDE",
                "reason": "missed punch",
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert submit.status_code == 200, submit.text
        corr_id = submit.json()["data"]["id"]
        workflow_request_id = submit.json()["data"]["workflow_request_id"]
        assert workflow_request_id is not None
        assert submit.json()["data"]["status"] == "PENDING"

        mgr_token = login(client, email=manager_user["email"], password=manager_user["password"])["access_token"]
        inbox = client.get("/api/v1/workflow/inbox?status=pending&limit=50", headers=_auth(mgr_token))
        assert inbox.status_code == 200, inbox.text
        assert any(i["id"] == workflow_request_id for i in inbox.json()["data"]["items"])

        appr = client.post(
            f"/api/v1/workflow/requests/{workflow_request_id}/approve",
            headers=_auth(mgr_token),
            json={"comment": "ok"},
        )
        assert appr.status_code == 200, appr.text

        mine = client.get("/api/v1/attendance/me/corrections?limit=50", headers=_auth(emp_token))
        assert mine.status_code == 200, mine.text
        row = next((r for r in mine.json()["data"]["items"] if r["id"] == corr_id), None)
        assert row is not None
        assert row["status"] == "APPROVED"

        # Override row exists
        with engine.connect() as conn:
            o = conn.execute(
                text(
                    """
                    SELECT override_kind, status
                    FROM attendance.day_overrides
                    WHERE tenant_id = :tenant_id
                      AND source_type = 'ATTENDANCE_CORRECTION'
                      AND source_id = :source_id
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "source_id": corr_id},
            ).first()
            assert o is not None
            assert str(o[0]) == "CORRECTION"
            assert str(o[1]) == "PRESENT_OVERRIDE"

        # Effective status reflects override
        days = client.get(
            f"/api/v1/attendance/me/days?from={day}&to={day}",
            headers=_auth(emp_token),
        )
        assert days.status_code == 200, days.text
        assert len(days.json()["data"]["items"]) == 1
        item = days.json()["data"]["items"][0]
        assert item["base_status"] == "ABSENT"
        assert item["effective_status"] == "PRESENT_OVERRIDE"
        assert item["override"] is not None
        assert item["override"]["kind"] == "CORRECTION"

        # Notifications: finalized notification for requester.
        from app.worker.notification_worker import consume_once

        consume_once(limit=50)
        emp_notifs = client.get("/api/v1/notifications?unread_only=1&limit=50", headers=_auth(emp_token))
        assert emp_notifs.status_code == 200, emp_notifs.text
        assert any(
            n["type"] == "workflow.request.finalized" and n["entity_id"] == workflow_request_id
            for n in emp_notifs.json()["data"]["items"]
        )

        # Audit rows exist for create + approved
        with engine.connect() as conn:
            cnt = int(
                conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM audit.audit_log
                        WHERE tenant_id = :tenant_id
                          AND entity_id = :entity_id
                          AND action IN ('attendance.correction.create','attendance.correction.approved')
                        """
                    ),
                    {"tenant_id": tenant["tenant_id"], "entity_id": corr_id},
                ).scalar()
                or 0
            )
            assert cnt >= 1
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_attendance_correction_conflicts_with_leave() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-att-leave")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-att-leave")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-att-leave")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.attendance.router_ess"))

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

        _create_workflow_definition_attendance_correction_manager_only(client, token=admin_token)

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        day1 = (datetime.now(timezone.utc).date() - timedelta(days=1))

        # Existing leave override blocks submission.
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO attendance.day_overrides (
                      tenant_id, employee_id, branch_id, day,
                      status, source_type, source_id, override_kind
                    ) VALUES (
                      :tenant_id, :employee_id, :branch_id, :day,
                      'ON_LEAVE', 'LEAVE_REQUEST', :source_id, 'LEAVE'
                    )
                    """
                ),
                {
                    "tenant_id": tenant["tenant_id"],
                    "employee_id": employee_emp_id,
                    "branch_id": tenant["branch_id"],
                    "day": day1,
                    "source_id": str(uuid.uuid4()),
                },
            )

        submit1 = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token),
            json={
                "day": day1.isoformat(),
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "PRESENT_OVERRIDE",
                "reason": "try",
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert submit1.status_code == 409, submit1.text
        assert submit1.json()["error"]["code"] == "attendance.correction.conflict.leave"

        # Approval re-check: introduce leave conflict after submission.
        day2 = (datetime.now(timezone.utc).date() - timedelta(days=2))
        submit2 = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token),
            json={
                "day": day2.isoformat(),
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "PRESENT_OVERRIDE",
                "reason": "ok",
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert submit2.status_code == 200, submit2.text
        corr_id = submit2.json()["data"]["id"]
        wf_id = submit2.json()["data"]["workflow_request_id"]

        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO attendance.day_overrides (
                      tenant_id, employee_id, branch_id, day,
                      status, source_type, source_id, override_kind
                    ) VALUES (
                      :tenant_id, :employee_id, :branch_id, :day,
                      'ON_LEAVE', 'LEAVE_REQUEST', :source_id, 'LEAVE'
                    )
                    """
                ),
                {
                    "tenant_id": tenant["tenant_id"],
                    "employee_id": employee_emp_id,
                    "branch_id": tenant["branch_id"],
                    "day": day2,
                    "source_id": str(uuid.uuid4()),
                },
            )

        mgr_token = login(client, email=manager_user["email"], password=manager_user["password"])["access_token"]
        appr = client.post(
            f"/api/v1/workflow/requests/{wf_id}/approve",
            headers=_auth(mgr_token),
            json={"comment": "approve"},
        )
        assert appr.status_code == 409, appr.text
        assert appr.json()["error"]["code"] == "attendance.correction.conflict.leave"

        # No correction override written.
        with engine.connect() as conn:
            cnt = int(
                conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM attendance.day_overrides
                        WHERE tenant_id = :tenant_id
                          AND source_type = 'ATTENDANCE_CORRECTION'
                          AND source_id = :source_id
                        """
                    ),
                    {"tenant_id": tenant["tenant_id"], "source_id": corr_id},
                ).scalar()
                or 0
            )
            assert cnt == 0
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_attendance_correction_tenant_isolation() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant_a = seed_tenant_company(engine)
    tenant_b = seed_tenant_company(engine)

    admin_a = seed_user(engine, tenant_id=tenant_a["tenant_id"], company_id=tenant_a["company_id"], branch_id=tenant_a["branch_id"], role_code="ADMIN", email_prefix="admin-att-a")
    manager_a = seed_user(engine, tenant_id=tenant_a["tenant_id"], company_id=tenant_a["company_id"], branch_id=tenant_a["branch_id"], role_code="MANAGER", email_prefix="mgr-att-a")
    employee_a = seed_user(engine, tenant_id=tenant_a["tenant_id"], company_id=tenant_a["company_id"], branch_id=tenant_a["branch_id"], role_code="EMPLOYEE", email_prefix="emp-att-a")

    admin_b = seed_user(engine, tenant_id=tenant_b["tenant_id"], company_id=tenant_b["company_id"], branch_id=tenant_b["branch_id"], role_code="ADMIN", email_prefix="admin-att-b")
    manager_b = seed_user(engine, tenant_id=tenant_b["tenant_id"], company_id=tenant_b["company_id"], branch_id=tenant_b["branch_id"], role_code="MANAGER", email_prefix="mgr-att-b")
    employee_b = seed_user(engine, tenant_id=tenant_b["tenant_id"], company_id=tenant_b["company_id"], branch_id=tenant_b["branch_id"], role_code="EMPLOYEE", email_prefix="emp-att-b")

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.attendance.router_ess"))

        # Setup tenant B correction
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

        _create_workflow_definition_attendance_correction_manager_only(client, token=token_b)

        emp_token_b = login(client, email=employee_b["email"], password=employee_b["password"])["access_token"]
        day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        submit_b = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token_b),
            json={
                "day": day,
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "PRESENT_OVERRIDE",
                "reason": "x",
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert submit_b.status_code == 200, submit_b.text
        corr_id_b = submit_b.json()["data"]["id"]

        # Setup tenant A employee (linked) and attempt to cancel tenant B correction.
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

        emp_token_a = login(client, email=employee_a["email"], password=employee_a["password"])["access_token"]
        cancel_other = client.post(
            f"/api/v1/attendance/me/corrections/{corr_id_b}/cancel",
            headers=_auth(emp_token_a),
        )
        assert cancel_other.status_code == 404, cancel_other.text
        assert cancel_other.json()["error"]["code"] == "attendance.correction.not_found"
    finally:
        cleanup(engine, tenant_id=tenant_a["tenant_id"], user_ids=[admin_a["user_id"], manager_a["user_id"], employee_a["user_id"]])
        cleanup(engine, tenant_id=tenant_b["tenant_id"], user_ids=[admin_b["user_id"], manager_b["user_id"], employee_b["user_id"]])


def test_attendance_correction_permission_denied_submit() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-att-deny")
    created_users = [manager_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.attendance.router_ess"))

        mgr_token = login(client, email=manager_user["email"], password=manager_user["password"])["access_token"]
        day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        submit = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(mgr_token),
            json={
                "day": day,
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "PRESENT_OVERRIDE",
                "reason": "x",
            },
        )
        assert submit.status_code == 403, submit.text
        assert submit.json()["error"]["code"] == "forbidden"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_attendance_correction_idempotent_create() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-att-idem")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-att-idem")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-att-idem")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.attendance.router_ess"))

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

        _create_workflow_definition_attendance_correction_manager_only(client, token=admin_token)

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        key = f"idem-{uuid.uuid4().hex}"

        r1 = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token),
            json={
                "day": day,
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "PRESENT_OVERRIDE",
                "reason": "x",
                "idempotency_key": key,
            },
        )
        assert r1.status_code == 200, r1.text
        cid1 = r1.json()["data"]["id"]

        r2 = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token),
            json={
                "day": day,
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "PRESENT_OVERRIDE",
                "reason": "x",
                "idempotency_key": key,
            },
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["data"]["id"] == cid1

        r3 = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token),
            json={
                "day": day,
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "ABSENT_OVERRIDE",
                "reason": "x",
                "idempotency_key": key,
            },
        )
        assert r3.status_code == 409, r3.text
        assert r3.json()["error"]["code"] == "attendance.correction.idempotency.conflict"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_attendance_correction_cancel_pending() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-att-cancel")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-att-cancel")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-att-cancel")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.attendance.router_ess"))

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

        _create_workflow_definition_attendance_correction_manager_only(client, token=admin_token)

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        submit = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token),
            json={
                "day": day,
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "PRESENT_OVERRIDE",
                "reason": "x",
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert submit.status_code == 200, submit.text
        corr_id = submit.json()["data"]["id"]

        cancel = client.post(
            f"/api/v1/attendance/me/corrections/{corr_id}/cancel",
            headers=_auth(emp_token),
        )
        assert cancel.status_code == 200, cancel.text
        assert cancel.json()["data"]["status"] == "CANCELED"

        with engine.connect() as conn:
            cnt = int(
                conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM attendance.day_overrides
                        WHERE tenant_id = :tenant_id
                          AND source_type = 'ATTENDANCE_CORRECTION'
                          AND source_id = :source_id
                        """
                    ),
                    {"tenant_id": tenant["tenant_id"], "source_id": corr_id},
                ).scalar()
                or 0
            )
            assert cnt == 0
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_attendance_correction_participant_only_cancel() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-att-part")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-att-part")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-att-part")
    outsider_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="outsider-att-part")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"], outsider_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.attendance.router_ess"))

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
            last_name="U",
            manager_employee_id=manager_emp_id,
        )
        link_user_to_employee(client, token=admin_token, employee_id=outsider_emp_id, user_id=outsider_user["user_id"])

        _create_workflow_definition_attendance_correction_manager_only(client, token=admin_token)

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        submit = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token),
            json={
                "day": day,
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "PRESENT_OVERRIDE",
                "reason": "x",
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert submit.status_code == 200, submit.text
        corr_id = submit.json()["data"]["id"]

        outsider_token = login(client, email=outsider_user["email"], password=outsider_user["password"])["access_token"]
        cancel_other = client.post(
            f"/api/v1/attendance/me/corrections/{corr_id}/cancel",
            headers=_auth(outsider_token),
        )
        assert cancel_other.status_code == 404, cancel_other.text
        assert cancel_other.json()["error"]["code"] == "attendance.correction.not_found"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_attendance_correction_pending_exists_for_day() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-att-pend")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-att-pend")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-att-pend")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.attendance.router_ess"))

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

        _create_workflow_definition_attendance_correction_manager_only(client, token=admin_token)

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()

        r1 = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token),
            json={
                "day": day,
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "PRESENT_OVERRIDE",
                "reason": "x",
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert r1.status_code == 200, r1.text

        r2 = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token),
            json={
                "day": day,
                "correction_type": "MARK_ABSENT",
                "requested_override_status": "ABSENT_OVERRIDE",
                "reason": "x",
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert r2.status_code == 409, r2.text
        assert r2.json()["error"]["code"] == "attendance.correction.pending_exists"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_attendance_workflow_non_assignee_cannot_approve() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-att-nonass")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-att-nonass")
    outsider = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="out-att-nonass")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-att-nonass")
    created_users = [admin["user_id"], manager_user["user_id"], outsider["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.attendance.router_ess"))

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

        _create_workflow_definition_attendance_correction_manager_only(client, token=admin_token)

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        submit = client.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token),
            json={
                "day": day,
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "PRESENT_OVERRIDE",
                "reason": "x",
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert submit.status_code == 200, submit.text
        wf_id = submit.json()["data"]["workflow_request_id"]

        outsider_token = login(client, email=outsider["email"], password=outsider["password"])["access_token"]
        attempt = client.post(
            f"/api/v1/workflow/requests/{wf_id}/approve",
            headers=_auth(outsider_token),
            json={"comment": "try"},
        )
        assert attempt.status_code == 403, attempt.text
        assert attempt.json()["error"]["code"] == "workflow.step.not_assignee"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_attendance_workflow_concurrent_approve_race() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-att-race")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-att-race")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-att-race")
    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client1 = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.attendance.router_ess"))
        client2 = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router", "app.domains.attendance.router_ess"))

        admin_token = login(client1, email=admin["email"], password=admin["password"])["access_token"]

        manager_emp_id = create_employee(
            client1,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="M",
            last_name="G",
        )
        link_user_to_employee(client1, token=admin_token, employee_id=manager_emp_id, user_id=manager_user["user_id"])

        employee_emp_id = create_employee(
            client1,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="E",
            last_name="E",
            manager_employee_id=manager_emp_id,
        )
        link_user_to_employee(client1, token=admin_token, employee_id=employee_emp_id, user_id=employee_user["user_id"])

        _create_workflow_definition_attendance_correction_manager_only(client1, token=admin_token)

        emp_token = login(client1, email=employee_user["email"], password=employee_user["password"])["access_token"]
        mgr_token = login(client1, email=manager_user["email"], password=manager_user["password"])["access_token"]

        day = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        submit = client1.post(
            "/api/v1/attendance/me/corrections",
            headers=_auth(emp_token),
            json={
                "day": day,
                "correction_type": "MARK_PRESENT",
                "requested_override_status": "PRESENT_OVERRIDE",
                "reason": "x",
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert submit.status_code == 200, submit.text
        corr_id = submit.json()["data"]["id"]
        wf_id = submit.json()["data"]["workflow_request_id"]

        def _approve(client, token: str) -> tuple[int, str]:
            r = client.post(
                f"/api/v1/workflow/requests/{wf_id}/approve",
                headers=_auth(token),
                json={"comment": "go"},
            )
            code = r.json().get("error", {}).get("code") if r.headers.get("content-type", "").startswith("application/json") else ""
            return r.status_code, code

        with ThreadPoolExecutor(max_workers=2) as ex:
            a = ex.submit(_approve, client1, mgr_token)
            b = ex.submit(_approve, client2, mgr_token)
            res = [a.result(), b.result()]

        statuses = sorted([r[0] for r in res])
        assert statuses == [200, 409], res
        assert any(code == "workflow.step.already_decided" for _st, code in res if _st == 409)

        # Handler is idempotent: only one override row for the correction source.
        with engine.connect() as conn:
            cnt = int(
                conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM attendance.day_overrides
                        WHERE tenant_id = :tenant_id
                          AND source_type = 'ATTENDANCE_CORRECTION'
                          AND source_id = :source_id
                        """
                    ),
                    {"tenant_id": tenant["tenant_id"], "source_id": corr_id},
                ).scalar()
                or 0
            )
            assert cnt == 1
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)
