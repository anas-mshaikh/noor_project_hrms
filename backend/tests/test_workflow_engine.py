from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

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


def _create_definition(
    client,
    *,
    token: str,
    request_type_code: str,
    code: str,
    name: str,
    version: int,
    steps: list[dict[str, object]],
) -> str:
    r = client.post(
        "/api/v1/workflow/definitions",
        headers=_auth(token),
        json={"request_type_code": request_type_code, "code": code, "name": name, "version": version},
    )
    assert r.status_code == 200, r.text
    definition_id = r.json()["data"]["id"]

    r2 = client.post(
        f"/api/v1/workflow/definitions/{definition_id}/steps",
        headers=_auth(token),
        json={"steps": steps},
    )
    assert r2.status_code == 200, r2.text

    r3 = client.post(
        f"/api/v1/workflow/definitions/{definition_id}/activate",
        headers=_auth(token),
    )
    assert r3.status_code == 200, r3.text
    return str(definition_id)


def test_workflow_happy_path_manager_then_role() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-wf",
    )
    manager_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="MANAGER",
        email_prefix="mgr-wf",
    )
    employee_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-wf",
    )
    hr_admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="HR_ADMIN",
        email_prefix="hradmin-wf",
    )

    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"], hr_admin["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.workflow.router",
                "app.domains.notifications.router",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        # Manager employee + link to manager user
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

        # Requester employee with manager chain
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

        # Definition: MANAGER -> ROLE(HR_ADMIN)
        _create_definition(
            client,
            token=admin_token,
            request_type_code="HR_PROFILE_CHANGE",
            code="HR_PROFILE_CHANGE_V1",
            name="HR Profile Change",
            version=1,
            steps=[
                {"step_index": 0, "assignee_type": "MANAGER"},
                {"step_index": 1, "assignee_type": "ROLE", "assignee_role_code": "HR_ADMIN"},
            ],
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        create = client.post(
            "/api/v1/workflow/requests",
            headers=_auth(emp_token),
            json={
                "request_type_code": "HR_PROFILE_CHANGE",
                "payload": {"field": "phone", "from": "x", "to": "y"},
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert create.status_code == 200, create.text
        request_id = create.json()["data"]["id"]

        mgr_token = login(client, email=manager_user["email"], password=manager_user["password"])["access_token"]
        inbox = client.get("/api/v1/workflow/inbox?status=pending&limit=50", headers=_auth(mgr_token))
        assert inbox.status_code == 200, inbox.text
        assert any(i["id"] == request_id for i in inbox.json()["data"]["items"])

        with engine.connect() as conn:
            outbox_id = conn.execute(
                text(
                    """
                    SELECT id
                    FROM workflow.notification_outbox
                    WHERE tenant_id = :tenant_id
                      AND recipient_user_id = :user_id
                      AND template_code = 'workflow.step.assigned'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "user_id": manager_user["user_id"]},
            ).scalar()
            assert outbox_id is not None

        from app.worker.notification_worker import consume_once

        consume_once(limit=50)

        mgr_notifs = client.get("/api/v1/notifications?unread_only=1&limit=50", headers=_auth(mgr_token))
        assert mgr_notifs.status_code == 200, mgr_notifs.text
        assert any(n["type"] == "workflow.step.assigned" and n["entity_id"] == request_id for n in mgr_notifs.json()["data"]["items"])

        # Manager approves -> HR_ADMIN inbox
        appr = client.post(
            f"/api/v1/workflow/requests/{request_id}/approve",
            headers=_auth(mgr_token),
            json={"comment": "ok"},
        )
        assert appr.status_code == 200, appr.text

        hr_token = login(client, email=hr_admin["email"], password=hr_admin["password"])["access_token"]
        inbox2 = client.get("/api/v1/workflow/inbox?status=pending&limit=50", headers=_auth(hr_token))
        assert inbox2.status_code == 200, inbox2.text
        assert any(i["id"] == request_id for i in inbox2.json()["data"]["items"])

        consume_once(limit=50)

        hr_notifs = client.get("/api/v1/notifications?unread_only=1&limit=50", headers=_auth(hr_token))
        assert hr_notifs.status_code == 200, hr_notifs.text
        assert any(n["type"] == "workflow.step.assigned" and n["entity_id"] == request_id for n in hr_notifs.json()["data"]["items"])

        # HR approves -> finalized
        appr2 = client.post(
            f"/api/v1/workflow/requests/{request_id}/approve",
            headers=_auth(hr_token),
            json={"comment": "approved"},
        )
        assert appr2.status_code == 200, appr2.text

        consume_once(limit=50)

        emp_notifs = client.get("/api/v1/notifications?unread_only=1&limit=50", headers=_auth(emp_token))
        assert emp_notifs.status_code == 200, emp_notifs.text
        assert any(n["type"] == "workflow.request.finalized" and n["entity_id"] == request_id for n in emp_notifs.json()["data"]["items"])

        # Audit rows for approvals
        with engine.connect() as conn:
            cnt = int(
                conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM audit.audit_log
                        WHERE tenant_id = :tenant_id
                          AND action = 'workflow.request.approve'
                          AND entity_id = :request_id
                        """
                    ),
                    {"tenant_id": tenant["tenant_id"], "request_id": request_id},
                ).scalar()
                or 0
            )
            assert cnt >= 2
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_workflow_tenant_isolation() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant_a = seed_tenant_company(engine)
    tenant_b = seed_tenant_company(engine)

    admin_a = seed_user(
        engine,
        tenant_id=tenant_a["tenant_id"],
        company_id=tenant_a["company_id"],
        branch_id=tenant_a["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-a",
    )
    admin_b = seed_user(
        engine,
        tenant_id=tenant_b["tenant_id"],
        company_id=tenant_b["company_id"],
        branch_id=tenant_b["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-b",
    )
    employee_b = seed_user(
        engine,
        tenant_id=tenant_b["tenant_id"],
        company_id=tenant_b["company_id"],
        branch_id=tenant_b["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-b",
    )

    created_users = [admin_a["user_id"], admin_b["user_id"], employee_b["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.workflow.router",
            )
        )

        token_b = login(client, email=admin_b["email"], password=admin_b["password"])["access_token"]

        # Link employee_b to an HR employee so they can submit a request.
        emp_id = create_employee(
            client,
            token=token_b,
            company_id=tenant_b["company_id"],
            branch_id=tenant_b["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Bob",
            last_name="B",
        )
        link_user_to_employee(client, token=token_b, employee_id=emp_id, user_id=employee_b["user_id"])

        # Single-step ROLE flow so no manager chain needed.
        _create_definition(
            client,
            token=token_b,
            request_type_code="HR_PROFILE_CHANGE",
            code="HR_PROFILE_CHANGE_B",
            name="HR Profile Change",
            version=1,
            steps=[{"step_index": 0, "assignee_type": "ROLE", "assignee_role_code": "ADMIN"}],
        )

        emp_token_b = login(client, email=employee_b["email"], password=employee_b["password"])["access_token"]
        create = client.post(
            "/api/v1/workflow/requests",
            headers=_auth(emp_token_b),
            json={"request_type_code": "HR_PROFILE_CHANGE", "payload": {"k": "v"}, "idempotency_key": f"idem-{uuid.uuid4().hex}"},
        )
        assert create.status_code == 200, create.text
        request_id = create.json()["data"]["id"]

        token_a = login(client, email=admin_a["email"], password=admin_a["password"])["access_token"]
        get_other = client.get(f"/api/v1/workflow/requests/{request_id}", headers=_auth(token_a))
        assert get_other.status_code == 404, get_other.text
    finally:
        cleanup(engine, tenant_id=tenant_a["tenant_id"], user_ids=[admin_a["user_id"]])
        cleanup(engine, tenant_id=tenant_b["tenant_id"], user_ids=[admin_b["user_id"], employee_b["user_id"]])


def test_workflow_permission_denied_submit() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    manager_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="MANAGER",
        email_prefix="mgr-nosubmit",
    )
    created_users = [manager_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.workflow.router"))
        mgr_token = login(client, email=manager_user["email"], password=manager_user["password"])["access_token"]

        r = client.post(
            "/api/v1/workflow/requests",
            headers=_auth(mgr_token),
            json={"request_type_code": "HR_PROFILE_CHANGE", "payload": {"x": 1}},
        )
        assert r.status_code == 403, r.text
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_workflow_non_assignee_cannot_approve() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-na")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-na")
    outsider = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="outsider-na")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-na")
    hr_admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="HR_ADMIN", email_prefix="hr-na")

    created_users = [admin["user_id"], manager_user["user_id"], outsider["user_id"], employee_user["user_id"], hr_admin["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router"))
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

        _create_definition(
            client,
            token=admin_token,
            request_type_code="HR_PROFILE_CHANGE",
            code="HR_PROFILE_CHANGE_NA",
            name="HR Profile Change",
            version=1,
            steps=[
                {"step_index": 0, "assignee_type": "MANAGER"},
                {"step_index": 1, "assignee_type": "ROLE", "assignee_role_code": "HR_ADMIN"},
            ],
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        create = client.post(
            "/api/v1/workflow/requests",
            headers=_auth(emp_token),
            json={"request_type_code": "HR_PROFILE_CHANGE", "payload": {"k": "v"}, "idempotency_key": f"idem-{uuid.uuid4().hex}"},
        )
        assert create.status_code == 200, create.text
        request_id = create.json()["data"]["id"]

        outsider_token = login(client, email=outsider["email"], password=outsider["password"])["access_token"]
        attempt = client.post(
            f"/api/v1/workflow/requests/{request_id}/approve",
            headers=_auth(outsider_token),
            json={"comment": "try"},
        )
        assert attempt.status_code == 403, attempt.text
        assert attempt.json()["error"]["code"] == "workflow.step.not_assignee"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_workflow_concurrent_approve_race() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-race")
    hr1 = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="HR_ADMIN", email_prefix="hr1-race")
    hr2 = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="HR_ADMIN", email_prefix="hr2-race")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-race")

    created_users = [admin["user_id"], hr1["user_id"], hr2["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client1 = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router"))
        client2 = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router"))

        admin_token = login(client1, email=admin["email"], password=admin["password"])["access_token"]

        emp_id = create_employee(
            client1,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Race",
            last_name="Req",
        )
        link_user_to_employee(client1, token=admin_token, employee_id=emp_id, user_id=employee_user["user_id"])

        # Single-step ROLE(HR_ADMIN) so both hr1/hr2 are assignees.
        _create_definition(
            client1,
            token=admin_token,
            request_type_code="HR_PROFILE_CHANGE",
            code="HR_PROFILE_CHANGE_RACE",
            name="HR Profile Change",
            version=1,
            steps=[{"step_index": 0, "assignee_type": "ROLE", "assignee_role_code": "HR_ADMIN"}],
        )

        emp_token = login(client1, email=employee_user["email"], password=employee_user["password"])["access_token"]
        create = client1.post(
            "/api/v1/workflow/requests",
            headers=_auth(emp_token),
            json={"request_type_code": "HR_PROFILE_CHANGE", "payload": {"k": "v"}, "idempotency_key": f"idem-{uuid.uuid4().hex}"},
        )
        assert create.status_code == 200, create.text
        request_id = create.json()["data"]["id"]

        hr1_token = login(client1, email=hr1["email"], password=hr1["password"])["access_token"]
        hr2_token = login(client2, email=hr2["email"], password=hr2["password"])["access_token"]

        def _approve(client, token: str) -> tuple[int, str]:
            r = client.post(
                f"/api/v1/workflow/requests/{request_id}/approve",
                headers=_auth(token),
                json={"comment": "go"},
            )
            code = r.json().get("error", {}).get("code") if r.headers.get("content-type", "").startswith("application/json") else ""
            return r.status_code, code

        with ThreadPoolExecutor(max_workers=2) as ex:
            a = ex.submit(_approve, client1, hr1_token)
            b = ex.submit(_approve, client2, hr2_token)
            res = [a.result(), b.result()]

        statuses = sorted([r[0] for r in res])
        assert statuses == [200, 409], res
        assert any(code == "workflow.step.already_decided" for _st, code in res if _st == 409)
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_workflow_idempotent_create() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-idem")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-idem")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-idem")

    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router"))
        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        mgr_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="I",
            last_name="Mgr",
        )
        link_user_to_employee(client, token=admin_token, employee_id=mgr_emp_id, user_id=manager_user["user_id"])

        emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="I",
            last_name="Emp",
            manager_employee_id=mgr_emp_id,
        )
        link_user_to_employee(client, token=admin_token, employee_id=emp_id, user_id=employee_user["user_id"])

        _create_definition(
            client,
            token=admin_token,
            request_type_code="HR_PROFILE_CHANGE",
            code="HR_PROFILE_CHANGE_IDEM",
            name="HR Profile Change",
            version=1,
            steps=[{"step_index": 0, "assignee_type": "MANAGER"}],
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        key = f"idem-{uuid.uuid4().hex}"

        r1 = client.post(
            "/api/v1/workflow/requests",
            headers=_auth(emp_token),
            json={"request_type_code": "HR_PROFILE_CHANGE", "payload": {"a": 1}, "idempotency_key": key},
        )
        assert r1.status_code == 200, r1.text
        rid1 = r1.json()["data"]["id"]

        r2 = client.post(
            "/api/v1/workflow/requests",
            headers=_auth(emp_token),
            json={"request_type_code": "HR_PROFILE_CHANGE", "payload": {"a": 1}, "idempotency_key": key},
        )
        assert r2.status_code == 200, r2.text
        rid2 = r2.json()["data"]["id"]
        assert rid1 == rid2

        with engine.connect() as conn:
            cnt = int(
                conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM workflow.notification_outbox
                        WHERE tenant_id = :tenant_id
                          AND recipient_user_id = :user_id
                          AND template_code = 'workflow.step.assigned'
                        """
                    ),
                    {"tenant_id": tenant["tenant_id"], "user_id": manager_user["user_id"]},
                ).scalar()
                or 0
            )
            assert cnt == 1
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_workflow_comment_and_attachment_participant_only() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-ca")
    manager_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="MANAGER", email_prefix="mgr-ca")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-ca")
    outsider = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="outsider-ca")

    created_users = [admin["user_id"], manager_user["user_id"], employee_user["user_id"], outsider["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr", "app.domains.workflow.router"))
        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        mgr_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="C",
            last_name="Mgr",
        )
        link_user_to_employee(client, token=admin_token, employee_id=mgr_emp_id, user_id=manager_user["user_id"])

        emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="C",
            last_name="Emp",
            manager_employee_id=mgr_emp_id,
        )
        link_user_to_employee(client, token=admin_token, employee_id=emp_id, user_id=employee_user["user_id"])

        _create_definition(
            client,
            token=admin_token,
            request_type_code="HR_PROFILE_CHANGE",
            code="HR_PROFILE_CHANGE_CA",
            name="HR Profile Change",
            version=1,
            steps=[{"step_index": 0, "assignee_type": "MANAGER"}],
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        create = client.post(
            "/api/v1/workflow/requests",
            headers=_auth(emp_token),
            json={"request_type_code": "HR_PROFILE_CHANGE", "payload": {"a": 1}, "idempotency_key": f"idem-{uuid.uuid4().hex}"},
        )
        assert create.status_code == 200, create.text
        request_id = create.json()["data"]["id"]

        mgr_token = login(client, email=manager_user["email"], password=manager_user["password"])["access_token"]
        c1 = client.post(
            f"/api/v1/workflow/requests/{request_id}/comments",
            headers=_auth(mgr_token),
            json={"body": "hello"},
        )
        assert c1.status_code == 200, c1.text

        outsider_token = login(client, email=outsider["email"], password=outsider["password"])["access_token"]
        c2 = client.post(
            f"/api/v1/workflow/requests/{request_id}/comments",
            headers=_auth(outsider_token),
            json={"body": "nope"},
        )
        assert c2.status_code == 404, c2.text
        assert c2.json()["error"]["code"] == "workflow.request.not_participant"

        # Seed a DMS file and attach it as a participant.
        file_id = uuid.uuid4()
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO dms.files (
                      id, tenant_id, storage_provider, bucket, object_key, content_type,
                      size_bytes, sha256, original_filename
                    ) VALUES (
                      :id, :tenant_id, 'local', NULL, :object_key, 'application/octet-stream',
                      0, NULL, 'test.txt'
                    )
                    """
                ),
                {"id": file_id, "tenant_id": tenant["tenant_id"], "object_key": f"test/{file_id.hex}/test.txt"},
            )

        a1 = client.post(
            f"/api/v1/workflow/requests/{request_id}/attachments",
            headers=_auth(mgr_token),
            json={"file_id": str(file_id), "note": "proof"},
        )
        assert a1.status_code == 200, a1.text

        a2 = client.post(
            f"/api/v1/workflow/requests/{request_id}/attachments",
            headers=_auth(outsider_token),
            json={"file_id": str(file_id), "note": "bad"},
        )
        assert a2.status_code == 404, a2.text
        assert a2.json()["error"]["code"] == "workflow.request.not_participant"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)

