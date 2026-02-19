from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
from sqlalchemy import create_engine, text

from tests.helpers.app import make_app
from tests.helpers.http import (
    auth_headers,
    create_employee,
    link_user_to_employee,
    login,
)
from tests.helpers.seed import cleanup, seed_tenant_company, seed_user


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping API integration tests",
)


def _create_workflow_definition_manager_only(
    client, *, token: str, request_type_code: str, code_prefix: str
) -> None:
    """
    Create a deterministic single-step workflow definition:
    - Step 0: MANAGER
    """

    r = client.post(
        "/api/v1/workflow/definitions",
        headers=auth_headers(token),
        json={
            "request_type_code": request_type_code,
            "code": f"{code_prefix}_{uuid.uuid4().hex[:6]}",
            "name": f"{request_type_code} (Manager only)",
            "version": 1,
        },
    )
    assert r.status_code == 200, r.text
    definition_id = r.json()["data"]["id"]

    r2 = client.post(
        f"/api/v1/workflow/definitions/{definition_id}/steps",
        headers=auth_headers(token),
        json={"steps": [{"step_index": 0, "assignee_type": "MANAGER"}]},
    )
    assert r2.status_code == 200, r2.text

    r3 = client.post(
        f"/api/v1/workflow/definitions/{definition_id}/activate",
        headers=auth_headers(token),
    )
    assert r3.status_code == 200, r3.text


def _create_workflow_definition_role(
    client, *, token: str, request_type_code: str, role_code: str, code_prefix: str
) -> None:
    """
    Create a deterministic single-step workflow definition:
    - Step 0: ROLE(role_code)
    """

    r = client.post(
        "/api/v1/workflow/definitions",
        headers=auth_headers(token),
        json={
            "request_type_code": request_type_code,
            "code": f"{code_prefix}_{uuid.uuid4().hex[:6]}",
            "name": f"{request_type_code} (Role {role_code})",
            "version": 1,
        },
    )
    assert r.status_code == 200, r.text
    definition_id = r.json()["data"]["id"]

    r2 = client.post(
        f"/api/v1/workflow/definitions/{definition_id}/steps",
        headers=auth_headers(token),
        json={
            "steps": [
                {
                    "step_index": 0,
                    "assignee_type": "ROLE",
                    "assignee_role_code": role_code,
                }
            ]
        },
    )
    assert r2.status_code == 200, r2.text

    r3 = client.post(
        f"/api/v1/workflow/definitions/{definition_id}/activate",
        headers=auth_headers(token),
    )
    assert r3.status_code == 200, r3.text


def test_onboarding_template_create_and_list_tenant_isolation() -> None:
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
        email_prefix="admin-onb-a",
    )
    admin_b = seed_user(
        engine,
        tenant_id=tenant_b["tenant_id"],
        company_id=tenant_b["company_id"],
        branch_id=tenant_b["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-onb-b",
    )
    created_users = [admin_a["user_id"], admin_b["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.onboarding.router_hr",
            )
        )

        token_a = login(client, email=admin_a["email"], password=admin_a["password"])[
            "access_token"
        ]
        token_b = login(client, email=admin_b["email"], password=admin_b["password"])[
            "access_token"
        ]

        # Tenant A creates a template.
        r = client.post(
            "/api/v1/onboarding/plan-templates",
            headers=auth_headers(token_a),
            json={"code": "ONB_V1", "name": "Onboarding V1", "is_active": True},
        )
        assert r.status_code == 200, r.text
        template_id_a = r.json()["data"]["id"]

        # Tenant B lists templates (should not see A's).
        r2 = client.get(
            "/api/v1/onboarding/plan-templates", headers=auth_headers(token_b)
        )
        assert r2.status_code == 200, r2.text
        assert all(t["id"] != template_id_a for t in r2.json()["data"])
    finally:
        cleanup(engine, tenant_id=tenant_a["tenant_id"], user_ids=created_users)
        cleanup(engine, tenant_id=tenant_b["tenant_id"], user_ids=[])


def test_onboarding_bundle_create_snapshots_tasks() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-onb-bundle",
    )
    created_users = [admin["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.onboarding.router_hr",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        employee_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Eve",
            last_name="Employee",
        )

        tmpl = client.post(
            "/api/v1/onboarding/plan-templates",
            headers=auth_headers(admin_token),
            json={
                "code": f"T{uuid.uuid4().hex[:6]}",
                "name": "Template",
                "is_active": True,
            },
        )
        assert tmpl.status_code == 200, tmpl.text
        template_id = tmpl.json()["data"]["id"]

        # Create two tasks with deterministic order.
        t1 = client.post(
            f"/api/v1/onboarding/plan-templates/{template_id}/tasks",
            headers=auth_headers(admin_token),
            json={
                "code": "FORM_1",
                "title": "Submit phone",
                "task_type": "FORM",
                "required": True,
                "order_index": 1,
                "assignee_type": "EMPLOYEE",
                "form_profile_change_mapping": {"phone": "phone"},
            },
        )
        assert t1.status_code == 200, t1.text

        t2 = client.post(
            f"/api/v1/onboarding/plan-templates/{template_id}/tasks",
            headers=auth_headers(admin_token),
            json={
                "code": "ACK_1",
                "title": "Acknowledge policy",
                "task_type": "ACK",
                "required": True,
                "order_index": 2,
                "assignee_type": "EMPLOYEE",
            },
        )
        assert t2.status_code == 200, t2.text

        bundle = client.post(
            f"/api/v1/onboarding/employees/{employee_id}/bundle",
            headers=auth_headers(admin_token),
            json={
                "template_code": tmpl.json()["data"]["code"],
                "branch_id": tenant["branch_id"],
            },
        )
        assert bundle.status_code == 200, bundle.text
        tasks = bundle.json()["data"]["tasks"]
        assert [t["task_code"] for t in tasks] == ["FORM_1", "ACK_1"]
        assert tasks[0]["title"] == "Submit phone"
        assert tasks[1]["title"] == "Acknowledge policy"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_ess_onboarding_access_participant_only() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-onb-po",
    )
    user1 = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-onb-1",
    )
    user2 = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-onb-2",
    )
    created_users = [admin["user_id"], user1["user_id"], user2["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.onboarding.router_hr",
                "app.domains.onboarding.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        emp1_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Emp",
            last_name="One",
        )
        link_user_to_employee(
            client, token=admin_token, employee_id=emp1_id, user_id=user1["user_id"]
        )

        emp2_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Emp",
            last_name="Two",
        )
        link_user_to_employee(
            client, token=admin_token, employee_id=emp2_id, user_id=user2["user_id"]
        )

        tmpl = client.post(
            "/api/v1/onboarding/plan-templates",
            headers=auth_headers(admin_token),
            json={
                "code": f"T{uuid.uuid4().hex[:6]}",
                "name": "Template",
                "is_active": True,
            },
        )
        assert tmpl.status_code == 200, tmpl.text
        template_id = tmpl.json()["data"]["id"]

        task = client.post(
            f"/api/v1/onboarding/plan-templates/{template_id}/tasks",
            headers=auth_headers(admin_token),
            json={
                "code": "FORM_1",
                "title": "Submit phone",
                "task_type": "FORM",
                "required": True,
                "order_index": 1,
                "assignee_type": "EMPLOYEE",
                "form_profile_change_mapping": {"phone": "phone"},
            },
        )
        assert task.status_code == 200, task.text

        bundle = client.post(
            f"/api/v1/onboarding/employees/{emp1_id}/bundle",
            headers=auth_headers(admin_token),
            json={
                "template_code": tmpl.json()["data"]["code"],
                "branch_id": tenant["branch_id"],
            },
        )
        assert bundle.status_code == 200, bundle.text
        task_id = bundle.json()["data"]["tasks"][0]["id"]

        token1 = login(client, email=user1["email"], password=user1["password"])[
            "access_token"
        ]
        token2 = login(client, email=user2["email"], password=user2["password"])[
            "access_token"
        ]

        me = client.get("/api/v1/ess/me/onboarding", headers=auth_headers(token1))
        assert me.status_code == 200, me.text
        assert me.json()["data"]["bundle"]["employee_id"] == emp1_id

        # Employee 2 cannot submit employee 1 task (participant-only 404).
        sub = client.post(
            f"/api/v1/ess/me/onboarding/tasks/{task_id}/submit-form",
            headers=auth_headers(token2),
            json={"payload": {"phone": "123"}},
        )
        assert sub.status_code == 404, sub.text
        assert sub.json()["error"]["code"] == "onboarding.task.not_found"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_document_task_upload_creates_dms_document_and_optional_verification() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-onb-doc",
    )
    hr_approver = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="HR_ADMIN",
        email_prefix="hr-onb-doc",
    )
    emp_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-onb-doc",
    )
    created_users = [admin["user_id"], hr_approver["user_id"], emp_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.workflow.router",
                "app.domains.dms.router_document_types",
                "app.domains.onboarding.router_hr",
                "app.domains.onboarding.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        # Workflow definition for document verification (HR_ADMIN role).
        _create_workflow_definition_role(
            client,
            token=admin_token,
            request_type_code="DOCUMENT_VERIFICATION",
            role_code="HR_ADMIN",
            code_prefix="DOCV",
        )

        # DMS doc type required by onboarding DOCUMENT task.
        dt = client.post(
            "/api/v1/dms/document-types",
            headers=auth_headers(admin_token),
            json={
                "code": "PASSPORT",
                "name": "Passport",
                "requires_expiry": True,
                "is_active": True,
            },
        )
        assert dt.status_code == 200, dt.text

        employee_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Doc",
            last_name="Employee",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=employee_id,
            user_id=emp_user["user_id"],
        )

        tmpl = client.post(
            "/api/v1/onboarding/plan-templates",
            headers=auth_headers(admin_token),
            json={
                "code": f"T{uuid.uuid4().hex[:6]}",
                "name": "Template",
                "is_active": True,
            },
        )
        assert tmpl.status_code == 200, tmpl.text
        template_id = tmpl.json()["data"]["id"]

        task = client.post(
            f"/api/v1/onboarding/plan-templates/{template_id}/tasks",
            headers=auth_headers(admin_token),
            json={
                "code": "DOC_1",
                "title": "Upload passport",
                "task_type": "DOCUMENT",
                "required": True,
                "order_index": 1,
                "assignee_type": "EMPLOYEE",
                "required_document_type_code": "PASSPORT",
                "requires_document_verification": True,
            },
        )
        assert task.status_code == 200, task.text

        bundle = client.post(
            f"/api/v1/onboarding/employees/{employee_id}/bundle",
            headers=auth_headers(admin_token),
            json={
                "template_code": tmpl.json()["data"]["code"],
                "branch_id": tenant["branch_id"],
            },
        )
        assert bundle.status_code == 200, bundle.text
        task_id = bundle.json()["data"]["tasks"][0]["id"]

        emp_token = login(
            client, email=emp_user["email"], password=emp_user["password"]
        )["access_token"]
        up = client.post(
            f"/api/v1/ess/me/onboarding/tasks/{task_id}/upload-document",
            headers=auth_headers(emp_token),
            files={"file": ("passport.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert up.status_code == 200, up.text
        assert up.json()["data"]["related_document_id"] is not None
        assert up.json()["data"]["verification_workflow_request_id"] is not None
        assert up.json()["data"]["status"] == "SUBMITTED"

        # DMS document exists for the employee.
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT d.id
                    FROM dms.documents d
                    WHERE d.tenant_id = :tenant_id
                      AND d.owner_employee_id = :employee_id
                    ORDER BY d.created_at DESC
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "employee_id": employee_id},
            ).fetchone()
            assert row is not None
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_submit_packet_creates_profile_change_request_idempotent() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-onb-pack",
    )
    manager_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="MANAGER",
        email_prefix="mgr-onb-pack",
    )
    emp_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-onb-pack",
    )
    created_users = [admin["user_id"], manager_user["user_id"], emp_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.workflow.router",
                "app.domains.onboarding.router_hr",
                "app.domains.onboarding.router_ess",
                "app.domains.profile_change.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        # Workflow definition for HR_PROFILE_CHANGE (MANAGER).
        _create_workflow_definition_manager_only(
            client,
            token=admin_token,
            request_type_code="HR_PROFILE_CHANGE",
            code_prefix="HRPC",
        )

        manager_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="Manny",
            last_name="Manager",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=manager_emp_id,
            user_id=manager_user["user_id"],
        )

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
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=employee_emp_id,
            user_id=emp_user["user_id"],
        )

        tmpl = client.post(
            "/api/v1/onboarding/plan-templates",
            headers=auth_headers(admin_token),
            json={
                "code": f"T{uuid.uuid4().hex[:6]}",
                "name": "Template",
                "is_active": True,
            },
        )
        assert tmpl.status_code == 200, tmpl.text
        template_id = tmpl.json()["data"]["id"]

        task = client.post(
            f"/api/v1/onboarding/plan-templates/{template_id}/tasks",
            headers=auth_headers(admin_token),
            json={
                "code": "FORM_1",
                "title": "Submit phone",
                "task_type": "FORM",
                "required": True,
                "order_index": 1,
                "assignee_type": "EMPLOYEE",
                "form_profile_change_mapping": {"phone": "phone"},
            },
        )
        assert task.status_code == 200, task.text

        bundle = client.post(
            f"/api/v1/onboarding/employees/{employee_emp_id}/bundle",
            headers=auth_headers(admin_token),
            json={
                "template_code": tmpl.json()["data"]["code"],
                "branch_id": tenant["branch_id"],
            },
        )
        assert bundle.status_code == 200, bundle.text
        bundle_id = bundle.json()["data"]["bundle"]["id"]
        task_id = bundle.json()["data"]["tasks"][0]["id"]

        emp_token = login(
            client, email=emp_user["email"], password=emp_user["password"]
        )["access_token"]
        sub = client.post(
            f"/api/v1/ess/me/onboarding/tasks/{task_id}/submit-form",
            headers=auth_headers(emp_token),
            json={"payload": {"phone": "+966500000000"}},
        )
        assert sub.status_code == 200, sub.text

        pkt1 = client.post(
            f"/api/v1/ess/me/onboarding/bundle/{bundle_id}/submit-packet",
            headers=auth_headers(emp_token),
        )
        assert pkt1.status_code == 200, pkt1.text
        req_id_1 = pkt1.json()["data"]["profile_change_request_id"]
        wf_id_1 = pkt1.json()["data"]["workflow_request_id"]

        pkt2 = client.post(
            f"/api/v1/ess/me/onboarding/bundle/{bundle_id}/submit-packet",
            headers=auth_headers(emp_token),
        )
        assert pkt2.status_code == 200, pkt2.text
        assert pkt2.json()["data"]["profile_change_request_id"] == req_id_1
        assert pkt2.json()["data"]["workflow_request_id"] == wf_id_1

        # Only one workflow request exists for that entity_id.
        with engine.connect() as conn:
            cnt = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM workflow.requests
                    WHERE tenant_id = :tenant_id
                      AND entity_type = 'hr_core.profile_change_request'
                      AND entity_id = :entity_id
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "entity_id": req_id_1},
            ).scalar()
            assert int(cnt or 0) == 1
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_profile_change_workflow_approve_applies_hr_core() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-hrpc",
    )
    manager_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="MANAGER",
        email_prefix="mgr-hrpc",
    )
    emp_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-hrpc",
    )
    created_users = [admin["user_id"], manager_user["user_id"], emp_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.workflow.router",
                "app.domains.notifications.router",
                "app.domains.profile_change.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        _create_workflow_definition_manager_only(
            client,
            token=admin_token,
            request_type_code="HR_PROFILE_CHANGE",
            code_prefix="HRPCAPP",
        )

        manager_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="Manny",
            last_name="Manager",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=manager_emp_id,
            user_id=manager_user["user_id"],
        )

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
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=employee_emp_id,
            user_id=emp_user["user_id"],
        )

        emp_token = login(
            client, email=emp_user["email"], password=emp_user["password"]
        )["access_token"]

        submit = client.post(
            "/api/v1/ess/me/profile-change-requests",
            headers=auth_headers(emp_token),
            json={
                "change_set": {
                    "phone": "+966511111111",
                    "address": {"line1": "Street 1"},
                    "bank_accounts": [
                        {
                            "iban": "SA0000000000000000000000",
                            "bank_name": "Bank",
                            "is_primary": True,
                        }
                    ],
                    "government_ids": [
                        {
                            "id_type": "NID",
                            "id_number": "123",
                            "issued_at": "2026-01-01",
                        }
                    ],
                    "dependents": [
                        {"name": "Kid", "relationship": "CHILD", "dob": "2020-01-01"}
                    ],
                },
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert submit.status_code == 200, submit.text
        request_id = submit.json()["data"]["id"]
        wf_request_id = submit.json()["data"]["workflow_request_id"]

        mgr_token = login(
            client, email=manager_user["email"], password=manager_user["password"]
        )["access_token"]
        appr = client.post(
            f"/api/v1/workflow/requests/{wf_request_id}/approve",
            headers=auth_headers(mgr_token),
            json={"comment": "ok"},
        )
        assert appr.status_code == 200, appr.text

        # hr_core updated
        with engine.connect() as conn:
            person = conn.execute(
                text(
                    """
                    SELECT p.phone, p.address
                    FROM hr_core.employees e
                    JOIN hr_core.persons p ON p.id = e.person_id
                    WHERE e.tenant_id = :tenant_id
                      AND e.id = :employee_id
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "employee_id": employee_emp_id},
            ).fetchone()
            assert person is not None
            assert person[0] == "+966511111111"

            bank_cnt = conn.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM hr_core.employee_bank_accounts
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "employee_id": employee_emp_id},
            ).scalar()
            assert int(bank_cnt or 0) == 1

            # Audit row exists.
            audit = conn.execute(
                text(
                    """
                    SELECT 1
                    FROM audit.audit_log
                    WHERE tenant_id = :tenant_id
                      AND entity_type = 'hr_core.profile_change_request'
                      AND entity_id = :entity_id
                      AND action = 'hr.profile_change.approved'
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "entity_id": request_id},
            ).fetchone()
            assert audit is not None

        # Deliver notifications and ensure ESS sees approval notification.
        from app.worker.notification_worker import consume_once

        consume_once(limit=50)
        notif = client.get(
            "/api/v1/notifications?unread_only=1&limit=50",
            headers=auth_headers(emp_token),
        )
        assert notif.status_code == 200, notif.text
        assert any(
            n["type"] == "hr.profile_change.approved"
            for n in notif.json()["data"]["items"]
        )
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_profile_change_reject_does_not_apply() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-hrpc-r",
    )
    manager_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="MANAGER",
        email_prefix="mgr-hrpc-r",
    )
    emp_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-hrpc-r",
    )
    created_users = [admin["user_id"], manager_user["user_id"], emp_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.workflow.router",
                "app.domains.profile_change.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]
        _create_workflow_definition_manager_only(
            client,
            token=admin_token,
            request_type_code="HR_PROFILE_CHANGE",
            code_prefix="HRPCRJ",
        )

        manager_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="Manny",
            last_name="Manager",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=manager_emp_id,
            user_id=manager_user["user_id"],
        )

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
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=employee_emp_id,
            user_id=emp_user["user_id"],
        )

        # Capture current phone before change request.
        with engine.connect() as conn:
            before_phone = conn.execute(
                text(
                    """
                    SELECT p.phone
                    FROM hr_core.employees e
                    JOIN hr_core.persons p ON p.id = e.person_id
                    WHERE e.tenant_id = :tenant_id
                      AND e.id = :employee_id
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "employee_id": employee_emp_id},
            ).scalar()

        emp_token = login(
            client, email=emp_user["email"], password=emp_user["password"]
        )["access_token"]
        submit = client.post(
            "/api/v1/ess/me/profile-change-requests",
            headers=auth_headers(emp_token),
            json={
                "change_set": {"phone": "+966522222222"},
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert submit.status_code == 200, submit.text
        wf_request_id = submit.json()["data"]["workflow_request_id"]

        mgr_token = login(
            client, email=manager_user["email"], password=manager_user["password"]
        )["access_token"]
        rej = client.post(
            f"/api/v1/workflow/requests/{wf_request_id}/reject",
            headers=auth_headers(mgr_token),
            json={"comment": "no"},
        )
        assert rej.status_code == 200, rej.text

        # Ensure phone did not change.
        with engine.connect() as conn:
            after_phone = conn.execute(
                text(
                    """
                    SELECT p.phone
                    FROM hr_core.employees e
                    JOIN hr_core.persons p ON p.id = e.person_id
                    WHERE e.tenant_id = :tenant_id
                      AND e.id = :employee_id
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "employee_id": employee_emp_id},
            ).scalar()
            assert after_phone == before_phone
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_concurrency_safety_profile_change_approve_race() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-hrpc-race",
    )
    manager_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="MANAGER",
        email_prefix="mgr-hrpc-race",
    )
    emp_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-hrpc-race",
    )
    created_users = [admin["user_id"], manager_user["user_id"], emp_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.workflow.router",
                "app.domains.profile_change.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]
        _create_workflow_definition_manager_only(
            client,
            token=admin_token,
            request_type_code="HR_PROFILE_CHANGE",
            code_prefix="HRPCRACE",
        )

        manager_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
            first_name="Manny",
            last_name="Manager",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=manager_emp_id,
            user_id=manager_user["user_id"],
        )

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
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=employee_emp_id,
            user_id=emp_user["user_id"],
        )

        emp_token = login(
            client, email=emp_user["email"], password=emp_user["password"]
        )["access_token"]
        submit = client.post(
            "/api/v1/ess/me/profile-change-requests",
            headers=auth_headers(emp_token),
            json={
                "change_set": {"phone": "+966533333333"},
                "idempotency_key": f"idem-{uuid.uuid4().hex}",
            },
        )
        assert submit.status_code == 200, submit.text
        wf_request_id = submit.json()["data"]["workflow_request_id"]

        mgr_token = login(
            client, email=manager_user["email"], password=manager_user["password"]
        )["access_token"]

        # First approval succeeds.
        appr1 = client.post(
            f"/api/v1/workflow/requests/{wf_request_id}/approve",
            headers=auth_headers(mgr_token),
            json={"comment": "ok"},
        )
        assert appr1.status_code == 200, appr1.text

        # Second approval should fail with workflow.step.already_decided.
        appr2 = client.post(
            f"/api/v1/workflow/requests/{wf_request_id}/approve",
            headers=auth_headers(mgr_token),
            json={"comment": "ok"},
        )
        assert appr2.status_code == 409, appr2.text
        assert appr2.json()["error"]["code"] == "workflow.step.already_decided"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)
