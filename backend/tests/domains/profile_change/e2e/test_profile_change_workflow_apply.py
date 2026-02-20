"""
HR Profile Change v1 E2E tests (workflow apply semantics).

This suite validates that:
- ESS can submit a profile change request (first-class domain row)
- Manager approval via Workflow Engine v1 applies changes to hr_core.* inside
  the same DB transaction via workflow terminal hooks
- Reject does not apply changes
- Approve decision is concurrency-safe (second approve => 409 already decided)
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import pytest
from sqlalchemy import text

from tests.factories.hr_core import create_employee, link_user_to_employee
from tests.factories.workflow import create_definition_manager_only
from tests.support.api_client import ApiClient
from tests.support.assertions import assert_error_code


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


def _setup_profile_change_chain(
    *,
    client_factory: Any,
    tenant_factory: Any,
    actor_factory: Any,
    include_notifications: bool,
) -> dict[str, Any]:
    """
    Build a small org graph for profile change workflow tests.

    Returns:
      - client: TestClient
      - tenant: TenantIds
      - api_admin/api_manager/api_emp: ApiClient wrappers
      - employee_id: the subject employee_id (hr_core.employees.id)

    Notes:
    - We create and link employees because MANAGER workflow assignment depends
      on employee manager relationships (hr_core.v_employee_current_employment).
    """

    routers = [
        "app.auth.router",
        "app.domains.hr_core.router_hr",
        "app.domains.workflow.router",
        "app.domains.profile_change.router_ess",
    ]
    if include_notifications:
        routers.append("app.domains.notifications.router")

    client = client_factory(routers)
    tenant = tenant_factory()

    admin = actor_factory(client, tenant, "ADMIN")
    manager_user = actor_factory(client, tenant, "MANAGER")
    emp_user = actor_factory(client, tenant, "EMPLOYEE")

    api_admin = ApiClient(client=client, headers=admin.headers())
    api_manager = ApiClient(client=client, headers=manager_user.headers())
    api_emp = ApiClient(client=client, headers=emp_user.headers())

    # Workflow definition for HR_PROFILE_CHANGE (single-step MANAGER).
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

    return {
        "client": client,
        "tenant": tenant,
        "api_admin": api_admin,
        "api_manager": api_manager,
        "api_emp": api_emp,
        "employee_id": employee_emp_id,
    }


def test_profile_change_workflow_approve_applies_hr_core(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ---------------------------------------------------------------------
    # Arrange
    # ---------------------------------------------------------------------
    ctx = _setup_profile_change_chain(
        client_factory=client_factory,
        tenant_factory=tenant_factory,
        actor_factory=actor_factory,
        include_notifications=True,
    )
    api_emp: ApiClient = ctx["api_emp"]
    api_manager: ApiClient = ctx["api_manager"]
    tenant = ctx["tenant"]
    employee_id = ctx["employee_id"]

    submit = api_emp.post(
        "/api/v1/ess/me/profile-change-requests",
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
    wf_request_id = submit["workflow_request_id"]
    request_id = submit["id"]

    # ---------------------------------------------------------------------
    # Act
    # ---------------------------------------------------------------------
    api_manager.post(
        f"/api/v1/workflow/requests/{wf_request_id}/approve",
        json={"comment": "ok"},
    )

    # ---------------------------------------------------------------------
    # Assert
    # ---------------------------------------------------------------------
    # hr_core updated (selected facts only; we do not re-assert every column).
    with db_engine.connect() as conn:
        person = conn.execute(
            text(
                """
                SELECT p.phone
                FROM hr_core.employees e
                JOIN hr_core.persons p ON p.id = e.person_id
                WHERE e.tenant_id = :tenant_id
                  AND e.id = :employee_id
                """
            ),
            {"tenant_id": tenant.tenant_id, "employee_id": employee_id},
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
            {"tenant_id": tenant.tenant_id, "employee_id": employee_id},
        ).scalar()
        assert int(bank_cnt or 0) == 1

        # Audit row exists for approval.
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
            {"tenant_id": tenant.tenant_id, "entity_id": request_id},
        ).fetchone()
        assert audit is not None

    # Deliver notifications and ensure ESS sees approval notification.
    from app.worker.notification_worker import consume_once

    consume_once(limit=50)
    notifs = api_emp.get("/api/v1/notifications", params={"unread_only": 1, "limit": 50})
    assert any(n["type"] == "hr.profile_change.approved" for n in notifs["items"])


def test_profile_change_reject_does_not_apply(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ---------------------------------------------------------------------
    # Arrange
    # ---------------------------------------------------------------------
    ctx = _setup_profile_change_chain(
        client_factory=client_factory,
        tenant_factory=tenant_factory,
        actor_factory=actor_factory,
        include_notifications=False,
    )
    api_emp: ApiClient = ctx["api_emp"]
    api_manager: ApiClient = ctx["api_manager"]
    tenant = ctx["tenant"]
    employee_id = ctx["employee_id"]

    # Capture current phone before change request.
    with db_engine.connect() as conn:
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
            {"tenant_id": tenant.tenant_id, "employee_id": employee_id},
        ).scalar()

    submit = api_emp.post(
        "/api/v1/ess/me/profile-change-requests",
        json={
            "change_set": {"phone": "+966522222222"},
            "idempotency_key": f"idem-{uuid.uuid4().hex}",
        },
    )
    wf_request_id = submit["workflow_request_id"]

    # ---------------------------------------------------------------------
    # Act
    # ---------------------------------------------------------------------
    api_manager.post(
        f"/api/v1/workflow/requests/{wf_request_id}/reject",
        json={"comment": "no"},
    )

    # ---------------------------------------------------------------------
    # Assert
    # ---------------------------------------------------------------------
    with db_engine.connect() as conn:
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
            {"tenant_id": tenant.tenant_id, "employee_id": employee_id},
        ).scalar()
        assert after_phone == before_phone


def test_concurrency_safety_profile_change_approve_race(
    client_factory,
    tenant_factory,
    actor_factory,
) -> None:
    # ---------------------------------------------------------------------
    # Arrange
    # ---------------------------------------------------------------------
    ctx = _setup_profile_change_chain(
        client_factory=client_factory,
        tenant_factory=tenant_factory,
        actor_factory=actor_factory,
        include_notifications=False,
    )
    client = ctx["client"]
    api_emp: ApiClient = ctx["api_emp"]
    api_manager: ApiClient = ctx["api_manager"]

    submit = api_emp.post(
        "/api/v1/ess/me/profile-change-requests",
        json={
            "change_set": {"phone": "+966533333333"},
            "idempotency_key": f"idem-{uuid.uuid4().hex}",
        },
    )
    wf_request_id = submit["workflow_request_id"]

    # ---------------------------------------------------------------------
    # Act
    # ---------------------------------------------------------------------
    api_manager.post(
        f"/api/v1/workflow/requests/{wf_request_id}/approve",
        json={"comment": "ok"},
    )

    appr2 = client.post(
        f"/api/v1/workflow/requests/{wf_request_id}/approve",
        headers=dict(api_manager.headers),
        json={"comment": "ok"},
    )

    # ---------------------------------------------------------------------
    # Assert
    # ---------------------------------------------------------------------
    assert appr2.status_code == 409, appr2.text
    assert_error_code(appr2.json(), code="workflow.step.already_decided")

