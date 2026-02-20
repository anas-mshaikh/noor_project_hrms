"""
Onboarding v2 API tests (templates + bundles).

These tests focus on HTTP-layer behavior for the onboarding v2 domain:
- tenant isolation (domain objects are tenant-scoped and must not leak)
- bundle creation snapshots template tasks deterministically (order + titles)
- ESS endpoints enforce participant-only access (404 to avoid leaking existence)
"""

from __future__ import annotations

import os
import uuid

import pytest

from tests.factories.hr_core import create_employee, link_user_to_employee
from tests.support.api_client import ApiClient
from tests.support.assertions import assert_error_code


pytestmark = [
    pytest.mark.api,
    pytest.mark.tenant,
    pytest.mark.rbac,
    pytest.mark.skipif(
        not os.getenv("DATABASE_URL"),
        reason="DATABASE_URL not set; skipping API integration tests",
    ),
]


def test_onboarding_template_create_and_list_tenant_isolation(
    client_factory,
    tenant_factory,
    actor_factory,
) -> None:
    # ---------------------------------------------------------------------
    # Arrange
    # ---------------------------------------------------------------------
    client = client_factory(
        [
            "app.auth.router",
            "app.domains.onboarding.router_hr",
        ]
    )

    tenant_a = tenant_factory()
    tenant_b = tenant_factory()

    admin_a = actor_factory(client, tenant_a, "ADMIN")
    admin_b = actor_factory(client, tenant_b, "ADMIN")

    api_a = ApiClient(client=client, headers=admin_a.headers())
    api_b = ApiClient(client=client, headers=admin_b.headers())

    # ---------------------------------------------------------------------
    # Act
    # ---------------------------------------------------------------------
    created = api_a.post(
        "/api/v1/onboarding/plan-templates",
        json={"code": "ONB_V1", "name": "Onboarding V1", "is_active": True},
    )
    listed_b = api_b.get("/api/v1/onboarding/plan-templates")

    # ---------------------------------------------------------------------
    # Assert
    # ---------------------------------------------------------------------
    assert all(t["id"] != created["id"] for t in listed_b)


def test_onboarding_bundle_create_snapshots_tasks(
    client_factory,
    tenant_factory,
    actor_factory,
) -> None:
    # ---------------------------------------------------------------------
    # Arrange
    # ---------------------------------------------------------------------
    client = client_factory(
        [
            "app.auth.router",
            "app.domains.hr_core.router_hr",
            "app.domains.onboarding.router_hr",
        ]
    )

    tenant = tenant_factory()
    admin = actor_factory(client, tenant, "ADMIN")
    api = ApiClient(client=client, headers=admin.headers())

    employee_id = create_employee(
        api,
        company_id=tenant.company_id,
        branch_id=tenant.branch_id,
        employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
        first_name="Eve",
        last_name="Employee",
    )

    template = api.post(
        "/api/v1/onboarding/plan-templates",
        json={
            "code": f"T{uuid.uuid4().hex[:6]}",
            "name": "Template",
            "is_active": True,
        },
    )
    template_id = template["id"]

    # Create two tasks with deterministic order.
    api.post(
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
    api.post(
        f"/api/v1/onboarding/plan-templates/{template_id}/tasks",
        json={
            "code": "ACK_1",
            "title": "Acknowledge policy",
            "task_type": "ACK",
            "required": True,
            "order_index": 2,
            "assignee_type": "EMPLOYEE",
        },
    )

    # ---------------------------------------------------------------------
    # Act
    # ---------------------------------------------------------------------
    bundle = api.post(
        f"/api/v1/onboarding/employees/{employee_id}/bundle",
        json={"template_code": template["code"], "branch_id": tenant.branch_id},
    )

    # ---------------------------------------------------------------------
    # Assert
    # ---------------------------------------------------------------------
    tasks = bundle["tasks"]
    assert [t["task_code"] for t in tasks] == ["FORM_1", "ACK_1"]
    assert tasks[0]["title"] == "Submit phone"
    assert tasks[1]["title"] == "Acknowledge policy"


def test_ess_onboarding_access_participant_only(
    client_factory,
    tenant_factory,
    actor_factory,
) -> None:
    # ---------------------------------------------------------------------
    # Arrange
    # ---------------------------------------------------------------------
    client = client_factory(
        [
            "app.auth.router",
            "app.domains.hr_core.router_hr",
            "app.domains.onboarding.router_hr",
            "app.domains.onboarding.router_ess",
        ]
    )

    tenant = tenant_factory()
    admin = actor_factory(client, tenant, "ADMIN")
    emp1_user = actor_factory(client, tenant, "EMPLOYEE")
    emp2_user = actor_factory(client, tenant, "EMPLOYEE")

    api_admin = ApiClient(client=client, headers=admin.headers())
    api_emp1 = ApiClient(client=client, headers=emp1_user.headers())

    emp1_id = create_employee(
        api_admin,
        company_id=tenant.company_id,
        branch_id=tenant.branch_id,
        employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
        first_name="Emp",
        last_name="One",
    )
    link_user_to_employee(
        api_admin,
        employee_id=emp1_id,
        user_id=emp1_user.user.user_id,
    )

    emp2_id = create_employee(
        api_admin,
        company_id=tenant.company_id,
        branch_id=tenant.branch_id,
        employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
        first_name="Emp",
        last_name="Two",
    )
    link_user_to_employee(
        api_admin,
        employee_id=emp2_id,
        user_id=emp2_user.user.user_id,
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
        f"/api/v1/onboarding/employees/{emp1_id}/bundle",
        json={"template_code": template["code"], "branch_id": tenant.branch_id},
    )
    task_id = bundle["tasks"][0]["id"]

    # ---------------------------------------------------------------------
    # Act
    # ---------------------------------------------------------------------
    me = api_emp1.get("/api/v1/ess/me/onboarding")

    # Employee 2 cannot submit employee 1 task (participant-only 404).
    sub = client.post(
        f"/api/v1/ess/me/onboarding/tasks/{task_id}/submit-form",
        headers=emp2_user.headers(),
        json={"payload": {"phone": "123"}},
    )

    # ---------------------------------------------------------------------
    # Assert
    # ---------------------------------------------------------------------
    assert me["bundle"]["employee_id"] == emp1_id

    assert sub.status_code == 404, sub.text
    assert_error_code(sub.json(), code="onboarding.task.not_found")

