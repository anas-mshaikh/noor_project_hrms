"""
Onboarding v2 E2E tests (cross-domain flows).

These tests intentionally span multiple domains because onboarding integrates:
- Workflow (definitions + request creation)
- DMS (document upload + optional verification workflow)
- HR profile change (packet submission creates a single HR_PROFILE_CHANGE request)

We keep the count small (test pyramid) but ensure the critical flows are covered.
"""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import text

from tests.factories.dms import create_document_type
from tests.factories.hr_core import create_employee, link_user_to_employee
from tests.factories.workflow import (
    create_definition_manager_only,
    create_definition_role,
)
from tests.support.api_client import ApiClient


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.api,
    pytest.mark.tenant,
    pytest.mark.rbac,
    pytest.mark.skipif(
        not os.getenv("DATABASE_URL"),
        reason="DATABASE_URL not set; skipping API integration tests",
    ),
]


def test_document_task_upload_creates_dms_document_and_optional_verification(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ---------------------------------------------------------------------
    # Arrange
    # ---------------------------------------------------------------------
    client = client_factory(
        [
            "app.auth.router",
            "app.domains.hr_core.router_hr",
            "app.domains.workflow.router",
            "app.domains.dms.router_document_types",
            "app.domains.onboarding.router_hr",
            "app.domains.onboarding.router_ess",
        ]
    )

    tenant = tenant_factory()
    admin = actor_factory(client, tenant, "ADMIN")
    _hr_approver = actor_factory(client, tenant, "HR_ADMIN")
    emp_user = actor_factory(client, tenant, "EMPLOYEE")

    api_admin = ApiClient(client=client, headers=admin.headers())

    # Workflow definition for document verification (HR_ADMIN role).
    create_definition_role(
        api_admin,
        request_type_code="DOCUMENT_VERIFICATION",
        role_code="HR_ADMIN",
        code_prefix="DOCV",
    )

    # DMS doc type required by onboarding DOCUMENT task.
    create_document_type(
        api_admin,
        code="PASSPORT",
        name="Passport",
        requires_expiry=True,
        is_active=True,
    )

    employee_id = create_employee(
        api_admin,
        company_id=tenant.company_id,
        branch_id=tenant.branch_id,
        employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
        first_name="Doc",
        last_name="Employee",
    )
    link_user_to_employee(
        api_admin,
        employee_id=employee_id,
        user_id=emp_user.user.user_id,
    )

    template = api_admin.post(
        "/api/v1/onboarding/plan-templates",
        json={
            "code": f"T{uuid.uuid4().hex[:6]}",
            "name": "Template",
            "is_active": True,
        },
    )
    template_id = template["id"]

    api_admin.post(
        f"/api/v1/onboarding/plan-templates/{template_id}/tasks",
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

    bundle = api_admin.post(
        f"/api/v1/onboarding/employees/{employee_id}/bundle",
        json={"template_code": template["code"], "branch_id": tenant.branch_id},
    )
    task_id = bundle["tasks"][0]["id"]

    # ---------------------------------------------------------------------
    # Act
    # ---------------------------------------------------------------------
    # We use the raw TestClient call here because this endpoint is multipart.
    up = client.post(
        f"/api/v1/ess/me/onboarding/tasks/{task_id}/upload-document",
        headers=emp_user.headers(),
        files={"file": ("passport.pdf", b"%PDF-1.4", "application/pdf")},
    )

    # ---------------------------------------------------------------------
    # Assert
    # ---------------------------------------------------------------------
    assert up.status_code == 200, up.text
    body = up.json()
    assert body.get("ok") is True, body
    data = body["data"]
    assert data["related_document_id"] is not None
    assert data["verification_workflow_request_id"] is not None
    assert data["status"] == "SUBMITTED"

    # DMS document exists for the employee.
    with db_engine.connect() as conn:
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
            {"tenant_id": tenant.tenant_id, "employee_id": employee_id},
        ).fetchone()
        assert row is not None


def test_submit_packet_creates_profile_change_request_idempotent(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ---------------------------------------------------------------------
    # Arrange
    # ---------------------------------------------------------------------
    client = client_factory(
        [
            "app.auth.router",
            "app.domains.hr_core.router_hr",
            "app.domains.workflow.router",
            "app.domains.onboarding.router_hr",
            "app.domains.onboarding.router_ess",
            # Included for completeness; packet submission creates a profile
            # change request using the same domain service + workflow hooks.
            "app.domains.profile_change.router_ess",
        ]
    )

    tenant = tenant_factory()
    admin = actor_factory(client, tenant, "ADMIN")
    manager_user = actor_factory(client, tenant, "MANAGER")
    emp_user = actor_factory(client, tenant, "EMPLOYEE")

    api_admin = ApiClient(client=client, headers=admin.headers())
    api_emp = ApiClient(client=client, headers=emp_user.headers())

    # Workflow definition for HR_PROFILE_CHANGE (MANAGER).
    create_definition_manager_only(
        api_admin,
        request_type_code="HR_PROFILE_CHANGE",
        code_prefix="HRPC",
    )

    manager_emp_id = create_employee(
        api_admin,
        company_id=tenant.company_id,
        branch_id=tenant.branch_id,
        employee_code=f"M{uuid.uuid4().hex[:6].upper()}",
        first_name="Manny",
        last_name="Manager",
    )
    link_user_to_employee(
        api_admin,
        employee_id=manager_emp_id,
        user_id=manager_user.user.user_id,
    )

    employee_emp_id = create_employee(
        api_admin,
        company_id=tenant.company_id,
        branch_id=tenant.branch_id,
        employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
        first_name="Eve",
        last_name="Employee",
        manager_employee_id=manager_emp_id,
    )
    link_user_to_employee(
        api_admin,
        employee_id=employee_emp_id,
        user_id=emp_user.user.user_id,
    )

    template = api_admin.post(
        "/api/v1/onboarding/plan-templates",
        json={
            "code": f"T{uuid.uuid4().hex[:6]}",
            "name": "Template",
            "is_active": True,
        },
    )
    template_id = template["id"]

    api_admin.post(
        f"/api/v1/onboarding/plan-templates/{template_id}/tasks",
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

    bundle = api_admin.post(
        f"/api/v1/onboarding/employees/{employee_emp_id}/bundle",
        json={"template_code": template["code"], "branch_id": tenant.branch_id},
    )
    bundle_id = bundle["bundle"]["id"]
    task_id = bundle["tasks"][0]["id"]

    api_emp.post(
        f"/api/v1/ess/me/onboarding/tasks/{task_id}/submit-form",
        json={"payload": {"phone": "+966500000000"}},
    )

    # ---------------------------------------------------------------------
    # Act
    # ---------------------------------------------------------------------
    pkt1 = api_emp.post(f"/api/v1/ess/me/onboarding/bundle/{bundle_id}/submit-packet")
    pkt2 = api_emp.post(f"/api/v1/ess/me/onboarding/bundle/{bundle_id}/submit-packet")

    # ---------------------------------------------------------------------
    # Assert
    # ---------------------------------------------------------------------
    assert pkt2["profile_change_request_id"] == pkt1["profile_change_request_id"]
    assert pkt2["workflow_request_id"] == pkt1["workflow_request_id"]

    # Only one workflow request exists for that entity_id (idempotent create).
    with db_engine.connect() as conn:
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
            {
                "tenant_id": tenant.tenant_id,
                "entity_id": pkt1["profile_change_request_id"],
            },
        ).scalar()
        assert int(cnt or 0) == 1

