from __future__ import annotations

import uuid
from datetime import date

import pytest
import sqlalchemy as sa

from tests.factories import hr_core as hr_core_factory
from tests.factories import workflow as workflow_factory
from tests.support.api_client import ApiClient


pytestmark = [pytest.mark.api, pytest.mark.tenant, pytest.mark.rbac]


def _insert_payable_workdays(
    db_engine,
    *,
    tenant_id: str,
    branch_id: str,
    employee_id: str,
    days: list[date],
    present_days: set[date],
    payable_minutes_present: int = 480,
) -> None:
    """
    Insert payable_day_summaries rows for deterministic payroll tests.

    We insert only WORKDAY rows. Missing days are treated as non-working days
    (weekly off/holiday/leave) by the upstream payable summary pipeline; payroll
    compute simply aggregates available rows.
    """

    with db_engine.begin() as conn:
        for d in days:
            presence = "PRESENT" if d in present_days else "ABSENT"
            payable_minutes = int(payable_minutes_present) if presence == "PRESENT" else 0
            conn.execute(
                sa.text(
                    """
                    INSERT INTO attendance.payable_day_summaries (
                      tenant_id,
                      branch_id,
                      employee_id,
                      day,
                      day_type,
                      presence_status,
                      expected_minutes,
                      worked_minutes,
                      payable_minutes
                    ) VALUES (
                      :tenant_id,
                      :branch_id,
                      :employee_id,
                      :day,
                      'WORKDAY',
                      :presence_status,
                      480,
                      :worked_minutes,
                      :payable_minutes
                    )
                    ON CONFLICT (tenant_id, employee_id, day)
                    DO UPDATE SET
                      branch_id = EXCLUDED.branch_id,
                      day_type = EXCLUDED.day_type,
                      presence_status = EXCLUDED.presence_status,
                      expected_minutes = EXCLUDED.expected_minutes,
                      worked_minutes = EXCLUDED.worked_minutes,
                      payable_minutes = EXCLUDED.payable_minutes,
                      computed_at = now()
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "branch_id": branch_id,
                    "employee_id": employee_id,
                    "day": d,
                    "presence_status": presence,
                    "worked_minutes": payable_minutes,
                    "payable_minutes": payable_minutes,
                },
            )


def _setup_payroll_app(
    *,
    client_factory,
    tenant_factory,
    actor_factory,
) -> dict[str, object]:
    client = client_factory(
        [
            "app.auth.router",
            "app.domains.hr_core.router_hr",
            "app.domains.workflow.router",
            "app.domains.notifications.router",
            "app.domains.payroll.router_admin",
            "app.domains.payroll.router_ess",
        ]
    )
    tenant = tenant_factory()

    admin = actor_factory(client, tenant, "ADMIN")
    hr_admin = actor_factory(client, tenant, "HR_ADMIN")
    emp_a = actor_factory(client, tenant, "EMPLOYEE")
    emp_b = actor_factory(client, tenant, "EMPLOYEE")

    admin_api = ApiClient(client=client, headers=admin.headers())
    hr_api = ApiClient(client=client, headers=hr_admin.headers())
    emp_a_api = ApiClient(client=client, headers=emp_a.headers())
    emp_b_api = ApiClient(client=client, headers=emp_b.headers())

    # Create two employees for payroll and link their ESS users.
    employee_a_id = hr_core_factory.create_employee(
        admin_api,
        company_id=tenant.company_id,
        branch_id=tenant.branch_id,
        employee_code=f"E{uuid.uuid4().hex[:6]}",
        first_name="EmpA",
        last_name="Test",
    )
    employee_b_id = hr_core_factory.create_employee(
        admin_api,
        company_id=tenant.company_id,
        branch_id=tenant.branch_id,
        employee_code=f"E{uuid.uuid4().hex[:6]}",
        first_name="EmpB",
        last_name="Test",
    )

    hr_core_factory.link_user_to_employee(admin_api, employee_id=employee_a_id, user_id=emp_a.user.user_id)
    hr_core_factory.link_user_to_employee(admin_api, employee_id=employee_b_id, user_id=emp_b.user.user_id)

    # Workflow engine requires requester user to be linked to an employee.
    # We link the HR_ADMIN user to a "payroll admin employee" in the same tenant.
    payroll_admin_employee_id = hr_core_factory.create_employee(
        admin_api,
        company_id=tenant.company_id,
        branch_id=tenant.branch_id,
        employee_code=f"PA{uuid.uuid4().hex[:6]}",
        first_name="Payroll",
        last_name="Admin",
    )
    hr_core_factory.link_user_to_employee(
        admin_api,
        employee_id=payroll_admin_employee_id,
        user_id=hr_admin.user.user_id,
    )

    return {
        "client": client,
        "tenant": tenant,
        "admin_api": admin_api,
        "hr_api": hr_api,
        "emp_a_api": emp_a_api,
        "emp_b_api": emp_b_api,
        "employee_a_id": employee_a_id,
        "employee_b_id": employee_b_id,
    }


def _create_basic_payroll_setup(hr_api: ApiClient) -> dict[str, str]:
    calendar = hr_api.post(
        "/api/v1/payroll/calendars",
        json={"code": f"CAL{uuid.uuid4().hex[:4]}", "name": "Monthly", "currency_code": "SAR", "timezone": "UTC"},
    )
    calendar_id = str(calendar["id"])

    period_key = "2026-01"
    hr_api.post(
        f"/api/v1/payroll/calendars/{calendar_id}/periods",
        json={"period_key": period_key, "start_date": "2026-01-01", "end_date": "2026-01-31"},
    )

    structure = hr_api.post(
        "/api/v1/payroll/salary-structures",
        json={"code": f"SS{uuid.uuid4().hex[:4]}", "name": "Base Only", "is_active": True},
    )
    structure_id = str(structure["id"])

    return {"calendar_id": calendar_id, "period_key": period_key, "structure_id": structure_id}


def _create_compensation(
    hr_api: ApiClient,
    *,
    employee_id: str,
    structure_id: str,
    base_amount: str,
) -> None:
    hr_api.post(
        f"/api/v1/payroll/employees/{employee_id}/compensation",
        json={
            "currency_code": "SAR",
            "salary_structure_id": structure_id,
            "base_amount": base_amount,
            "effective_from": "2026-01-01",
            "effective_to": None,
        },
    )


def test_payrun_generate_idempotent(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ------------------------------------------------------------------
    # Arrange
    # ------------------------------------------------------------------
    ctx = _setup_payroll_app(client_factory=client_factory, tenant_factory=tenant_factory, actor_factory=actor_factory)
    tenant = ctx["tenant"]
    hr_api: ApiClient = ctx["hr_api"]
    employee_a_id = ctx["employee_a_id"]

    setup = _create_basic_payroll_setup(hr_api)
    _create_compensation(hr_api, employee_id=employee_a_id, structure_id=setup["structure_id"], base_amount="1000.00")

    # Insert a minimal payable summary row so the employee is INCLUDED.
    _insert_payable_workdays(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=employee_a_id,
        days=[date(2026, 1, 1)],
        present_days={date(2026, 1, 1)},
    )

    # ------------------------------------------------------------------
    # Act
    # ------------------------------------------------------------------
    payrun1 = hr_api.post(
        "/api/v1/payroll/payruns/generate",
        json={
            "calendar_id": setup["calendar_id"],
            "period_key": setup["period_key"],
            "idempotency_key": "k1",
        },
    )
    payrun2 = hr_api.post(
        "/api/v1/payroll/payruns/generate",
        json={
            "calendar_id": setup["calendar_id"],
            "period_key": setup["period_key"],
            "idempotency_key": "k1",
        },
    )

    # ------------------------------------------------------------------
    # Assert
    # ------------------------------------------------------------------
    assert str(payrun1["id"]) == str(payrun2["id"])

    with db_engine.connect() as conn:
        pr_cnt = conn.execute(
            sa.text(
                """
                SELECT COUNT(*)
                FROM payroll.payruns
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant.tenant_id, "id": payrun1["id"]},
        ).scalar()
        assert int(pr_cnt or 0) == 1

        item_cnt = conn.execute(
            sa.text(
                """
                SELECT COUNT(*)
                FROM payroll.payrun_items
                WHERE tenant_id = :tenant_id
                  AND payrun_id = :payrun_id
                """
            ),
            {"tenant_id": tenant.tenant_id, "payrun_id": payrun1["id"]},
        ).scalar()
        assert int(item_cnt or 0) >= 1


def test_payrun_generation_uses_payable_days_proration(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ------------------------------------------------------------------
    # Arrange
    # ------------------------------------------------------------------
    ctx = _setup_payroll_app(client_factory=client_factory, tenant_factory=tenant_factory, actor_factory=actor_factory)
    tenant = ctx["tenant"]
    hr_api: ApiClient = ctx["hr_api"]
    employee_a_id = ctx["employee_a_id"]

    setup = _create_basic_payroll_setup(hr_api)
    _create_compensation(hr_api, employee_id=employee_a_id, structure_id=setup["structure_id"], base_amount="1000.00")

    days = [date(2026, 1, d) for d in range(1, 21)]
    present = {date(2026, 1, d) for d in range(1, 11)}
    _insert_payable_workdays(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=employee_a_id,
        days=days,
        present_days=present,
    )

    # ------------------------------------------------------------------
    # Act
    # ------------------------------------------------------------------
    payrun = hr_api.post(
        "/api/v1/payroll/payruns/generate",
        json={
            "calendar_id": setup["calendar_id"],
            "period_key": setup["period_key"],
            "idempotency_key": "k2",
        },
    )

    # ------------------------------------------------------------------
    # Assert
    # ------------------------------------------------------------------
    with db_engine.connect() as conn:
        row = conn.execute(
            sa.text(
                """
                SELECT payable_days, working_days_in_period, gross_amount, net_amount
                FROM payroll.payrun_items
                WHERE tenant_id = :tenant_id
                  AND payrun_id = :payrun_id
                  AND employee_id = :employee_id
                """
            ),
            {"tenant_id": tenant.tenant_id, "payrun_id": payrun["id"], "employee_id": employee_a_id},
        ).mappings().first()
        assert row is not None
        assert int(row["payable_days"]) == 10
        assert int(row["working_days_in_period"]) == 20
        assert str(row["gross_amount"]) == "500.00"
        assert str(row["net_amount"]) == "500.00"


def test_payrun_submit_and_workflow_approve_transitions_status(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ------------------------------------------------------------------
    # Arrange
    # ------------------------------------------------------------------
    ctx = _setup_payroll_app(client_factory=client_factory, tenant_factory=tenant_factory, actor_factory=actor_factory)
    tenant = ctx["tenant"]
    admin_api: ApiClient = ctx["admin_api"]
    hr_api: ApiClient = ctx["hr_api"]
    employee_a_id = ctx["employee_a_id"]

    setup = _create_basic_payroll_setup(hr_api)
    _create_compensation(hr_api, employee_id=employee_a_id, structure_id=setup["structure_id"], base_amount="1000.00")
    _insert_payable_workdays(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=employee_a_id,
        days=[date(2026, 1, 1)],
        present_days={date(2026, 1, 1)},
    )

    # Workflow definition for PAYRUN_APPROVAL (ROLE HR_ADMIN).
    workflow_factory.create_definition_role(
        admin_api,
        request_type_code="PAYRUN_APPROVAL",
        role_code="HR_ADMIN",
        code_prefix="PAYRUN",
    )

    payrun = hr_api.post(
        "/api/v1/payroll/payruns/generate",
        json={
            "calendar_id": setup["calendar_id"],
            "period_key": setup["period_key"],
            "idempotency_key": "k3",
        },
    )

    # ------------------------------------------------------------------
    # Act
    # ------------------------------------------------------------------
    submitted = hr_api.post(f"/api/v1/payroll/payruns/{payrun['id']}/submit-approval", json={})

    # Approve via workflow endpoint (HR_ADMIN is the assignee).
    hr_api.post(f"/api/v1/workflow/requests/{submitted['workflow_request_id']}/approve", json={})

    # ------------------------------------------------------------------
    # Assert
    # ------------------------------------------------------------------
    payrun_after = hr_api.get(f"/api/v1/payroll/payruns/{payrun['id']}", params={"include_lines": 0})
    assert str(payrun_after["payrun"]["status"]) == "APPROVED"

    with db_engine.connect() as conn:
        audit = conn.execute(
            sa.text(
                """
                SELECT 1
                FROM audit.audit_log
                WHERE tenant_id = :tenant_id
                  AND entity_type = 'payroll.payrun'
                  AND entity_id = :payrun_id
                  AND action = 'payroll.payrun.approved'
                LIMIT 1
                """
            ),
            {"tenant_id": tenant.tenant_id, "payrun_id": payrun["id"]},
        ).fetchone()
        assert audit is not None


def test_payrun_publish_creates_payslips_and_dms_docs(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ------------------------------------------------------------------
    # Arrange
    # ------------------------------------------------------------------
    ctx = _setup_payroll_app(client_factory=client_factory, tenant_factory=tenant_factory, actor_factory=actor_factory)
    tenant = ctx["tenant"]
    admin_api: ApiClient = ctx["admin_api"]
    hr_api: ApiClient = ctx["hr_api"]
    emp_a_api: ApiClient = ctx["emp_a_api"]
    employee_a_id = ctx["employee_a_id"]

    setup = _create_basic_payroll_setup(hr_api)
    _create_compensation(hr_api, employee_id=employee_a_id, structure_id=setup["structure_id"], base_amount="1000.00")
    _insert_payable_workdays(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=employee_a_id,
        days=[date(2026, 1, 1)],
        present_days={date(2026, 1, 1)},
    )

    workflow_factory.create_definition_role(
        admin_api,
        request_type_code="PAYRUN_APPROVAL",
        role_code="HR_ADMIN",
        code_prefix="PAYRUN",
    )

    payrun = hr_api.post(
        "/api/v1/payroll/payruns/generate",
        json={
            "calendar_id": setup["calendar_id"],
            "period_key": setup["period_key"],
            "idempotency_key": "k4",
        },
    )
    submitted = hr_api.post(f"/api/v1/payroll/payruns/{payrun['id']}/submit-approval", json={})
    hr_api.post(f"/api/v1/workflow/requests/{submitted['workflow_request_id']}/approve", json={})

    # ------------------------------------------------------------------
    # Act
    # ------------------------------------------------------------------
    published = hr_api.post(f"/api/v1/payroll/payruns/{payrun['id']}/publish", json={})

    # ------------------------------------------------------------------
    # Assert
    # ------------------------------------------------------------------
    assert int(published["published_count"]) >= 1

    with db_engine.connect() as conn:
        slip = conn.execute(
            sa.text(
                """
                SELECT id, dms_document_id
                FROM payroll.payslips
                WHERE tenant_id = :tenant_id
                  AND payrun_id = :payrun_id
                  AND employee_id = :employee_id
                """
            ),
            {"tenant_id": tenant.tenant_id, "payrun_id": payrun["id"], "employee_id": employee_a_id},
        ).mappings().first()
        assert slip is not None
        assert slip["dms_document_id"] is not None

        doc = conn.execute(
            sa.text(
                """
                SELECT 1
                FROM dms.documents d
                JOIN dms.document_types dt ON dt.id = d.document_type_id
                WHERE d.tenant_id = :tenant_id
                  AND d.id = :document_id
                  AND dt.code = 'PAYSLIP'
                  AND d.owner_employee_id = :employee_id
                LIMIT 1
                """
            ),
            {
                "tenant_id": tenant.tenant_id,
                "document_id": slip["dms_document_id"],
                "employee_id": employee_a_id,
            },
        ).fetchone()
        assert doc is not None

    # Deliver notifications and ensure ESS sees a payslip published notification.
    from app.worker.notification_worker import consume_once

    consume_once(limit=50)
    notifs = emp_a_api.get("/api/v1/notifications", params={"unread_only": 1, "limit": 50})
    assert any(n["type"] == "payroll.payslip.published" for n in notifs["items"])


def test_employee_can_only_read_own_payslip(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ------------------------------------------------------------------
    # Arrange
    # ------------------------------------------------------------------
    ctx = _setup_payroll_app(client_factory=client_factory, tenant_factory=tenant_factory, actor_factory=actor_factory)
    tenant = ctx["tenant"]
    admin_api: ApiClient = ctx["admin_api"]
    hr_api: ApiClient = ctx["hr_api"]
    emp_a_api: ApiClient = ctx["emp_a_api"]
    emp_b_api: ApiClient = ctx["emp_b_api"]
    employee_a_id = ctx["employee_a_id"]
    employee_b_id = ctx["employee_b_id"]

    setup = _create_basic_payroll_setup(hr_api)
    _create_compensation(hr_api, employee_id=employee_a_id, structure_id=setup["structure_id"], base_amount="1000.00")
    _create_compensation(hr_api, employee_id=employee_b_id, structure_id=setup["structure_id"], base_amount="1000.00")

    _insert_payable_workdays(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=employee_a_id,
        days=[date(2026, 1, 1)],
        present_days={date(2026, 1, 1)},
    )
    _insert_payable_workdays(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=employee_b_id,
        days=[date(2026, 1, 1)],
        present_days={date(2026, 1, 1)},
    )

    workflow_factory.create_definition_role(
        admin_api,
        request_type_code="PAYRUN_APPROVAL",
        role_code="HR_ADMIN",
        code_prefix="PAYRUN",
    )

    payrun = hr_api.post(
        "/api/v1/payroll/payruns/generate",
        json={
            "calendar_id": setup["calendar_id"],
            "period_key": setup["period_key"],
            "idempotency_key": "k5",
        },
    )
    submitted = hr_api.post(f"/api/v1/payroll/payruns/{payrun['id']}/submit-approval", json={})
    hr_api.post(f"/api/v1/workflow/requests/{submitted['workflow_request_id']}/approve", json={})
    hr_api.post(f"/api/v1/payroll/payruns/{payrun['id']}/publish", json={})

    # Get payslip IDs for both employees.
    slips_a = emp_a_api.get("/api/v1/ess/me/payslips", params={"year": 2026})
    slips_b = emp_b_api.get("/api/v1/ess/me/payslips", params={"year": 2026})
    assert slips_a["items"]
    assert slips_b["items"]

    payslip_b_id = slips_b["items"][0]["id"]

    # ------------------------------------------------------------------
    # Act / Assert
    # ------------------------------------------------------------------
    # Employee A cannot read or download employee B's payslip (participant-safe 404).
    r = emp_a_api.raw_get(f"/api/v1/ess/me/payslips/{payslip_b_id}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "payroll.payslip.not_found"

    r = emp_a_api.raw_get(f"/api/v1/ess/me/payslips/{payslip_b_id}/download")
    assert r.status_code == 404
    assert r.headers.get("content-type", "").startswith("application/json")
    assert r.json()["error"]["code"] == "payroll.payslip.not_found"


def test_payrun_invalid_state_errors(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ------------------------------------------------------------------
    # Arrange
    # ------------------------------------------------------------------
    ctx = _setup_payroll_app(client_factory=client_factory, tenant_factory=tenant_factory, actor_factory=actor_factory)
    tenant = ctx["tenant"]
    admin_api: ApiClient = ctx["admin_api"]
    hr_api: ApiClient = ctx["hr_api"]
    employee_a_id = ctx["employee_a_id"]

    setup = _create_basic_payroll_setup(hr_api)
    _create_compensation(hr_api, employee_id=employee_a_id, structure_id=setup["structure_id"], base_amount="1000.00")
    _insert_payable_workdays(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=employee_a_id,
        days=[date(2026, 1, 1)],
        present_days={date(2026, 1, 1)},
    )

    workflow_factory.create_definition_role(
        admin_api,
        request_type_code="PAYRUN_APPROVAL",
        role_code="HR_ADMIN",
        code_prefix="PAYRUN",
    )

    payrun = hr_api.post(
        "/api/v1/payroll/payruns/generate",
        json={
            "calendar_id": setup["calendar_id"],
            "period_key": setup["period_key"],
            "idempotency_key": "k6",
        },
    )

    # ------------------------------------------------------------------
    # Act / Assert
    # ------------------------------------------------------------------
    # Publish before approval -> 409 payroll.payrun.not_approved
    r = hr_api.raw_get(f"/api/v1/payroll/payruns/{payrun['id']}/publish")
    assert r.status_code == 405  # GET not allowed; use POST

    r = hr_api.client.post(  # raw client, because ApiClient unwraps
        f"/api/v1/payroll/payruns/{payrun['id']}/publish",
        headers=hr_api.headers,
        json={},
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "payroll.payrun.not_approved"

    submitted = hr_api.post(f"/api/v1/payroll/payruns/{payrun['id']}/submit-approval", json={})
    hr_api.post(f"/api/v1/workflow/requests/{submitted['workflow_request_id']}/approve", json={})

    hr_api.post(f"/api/v1/payroll/payruns/{payrun['id']}/publish", json={})

    # Publish twice -> already_published
    r2 = hr_api.client.post(
        f"/api/v1/payroll/payruns/{payrun['id']}/publish",
        headers=hr_api.headers,
        json={},
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "payroll.payrun.already_published"


def test_tenant_isolation_payrun_and_payslip(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ------------------------------------------------------------------
    # Arrange: tenant A creates a payrun and publishes payslips
    # ------------------------------------------------------------------
    ctx_a = _setup_payroll_app(client_factory=client_factory, tenant_factory=tenant_factory, actor_factory=actor_factory)
    tenant_a = ctx_a["tenant"]
    admin_api_a: ApiClient = ctx_a["admin_api"]
    hr_api_a: ApiClient = ctx_a["hr_api"]
    emp_a_api: ApiClient = ctx_a["emp_a_api"]
    employee_a_id = ctx_a["employee_a_id"]

    setup = _create_basic_payroll_setup(hr_api_a)
    _create_compensation(hr_api_a, employee_id=employee_a_id, structure_id=setup["structure_id"], base_amount="1000.00")
    _insert_payable_workdays(
        db_engine,
        tenant_id=tenant_a.tenant_id,
        branch_id=tenant_a.branch_id,
        employee_id=employee_a_id,
        days=[date(2026, 1, 1)],
        present_days={date(2026, 1, 1)},
    )
    workflow_factory.create_definition_role(
        admin_api_a,
        request_type_code="PAYRUN_APPROVAL",
        role_code="HR_ADMIN",
        code_prefix="PAYRUN",
    )
    payrun = hr_api_a.post(
        "/api/v1/payroll/payruns/generate",
        json={
            "calendar_id": setup["calendar_id"],
            "period_key": setup["period_key"],
            "idempotency_key": "k7",
        },
    )
    submitted = hr_api_a.post(f"/api/v1/payroll/payruns/{payrun['id']}/submit-approval", json={})
    hr_api_a.post(f"/api/v1/workflow/requests/{submitted['workflow_request_id']}/approve", json={})
    hr_api_a.post(f"/api/v1/payroll/payruns/{payrun['id']}/publish", json={})

    slips = emp_a_api.get("/api/v1/ess/me/payslips", params={"year": 2026})
    assert slips["items"]
    payslip_id = slips["items"][0]["id"]

    # ------------------------------------------------------------------
    # Arrange: tenant B cannot access tenant A artifacts
    # ------------------------------------------------------------------
    client_b = client_factory(
        [
            "app.auth.router",
            "app.domains.hr_core.router_hr",
            "app.domains.payroll.router_admin",
            "app.domains.payroll.router_ess",
        ]
    )
    tenant_b = tenant_factory()
    admin_b = actor_factory(client_b, tenant_b, "ADMIN")
    hr_admin_b = actor_factory(client_b, tenant_b, "HR_ADMIN")
    emp_b = actor_factory(client_b, tenant_b, "EMPLOYEE")

    admin_api_b = ApiClient(client=client_b, headers=admin_b.headers())
    hr_api_b = ApiClient(client=client_b, headers=hr_admin_b.headers())
    emp_api_b = ApiClient(client=client_b, headers=emp_b.headers())

    # Link the tenant B employee actor to an employee so ESS endpoints don't fail with ess.not_linked.
    employee_b_id = hr_core_factory.create_employee(
        admin_api_b,
        company_id=tenant_b.company_id,
        branch_id=tenant_b.branch_id,
        employee_code=f"TB{uuid.uuid4().hex[:6]}",
        first_name="TenantB",
        last_name="Emp",
    )
    hr_core_factory.link_user_to_employee(admin_api_b, employee_id=employee_b_id, user_id=emp_b.user.user_id)

    # ------------------------------------------------------------------
    # Act / Assert
    # ------------------------------------------------------------------
    r = hr_api_b.raw_get(f"/api/v1/payroll/payruns/{payrun['id']}")
    assert r.status_code == 404

    r = emp_api_b.raw_get(f"/api/v1/ess/me/payslips/{payslip_id}")
    assert r.status_code == 404


def test_concurrency_locking_publish_double_call(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ------------------------------------------------------------------
    # Arrange
    # ------------------------------------------------------------------
    ctx = _setup_payroll_app(client_factory=client_factory, tenant_factory=tenant_factory, actor_factory=actor_factory)
    tenant = ctx["tenant"]
    admin_api: ApiClient = ctx["admin_api"]
    hr_api: ApiClient = ctx["hr_api"]
    employee_a_id = ctx["employee_a_id"]

    setup = _create_basic_payroll_setup(hr_api)
    _create_compensation(hr_api, employee_id=employee_a_id, structure_id=setup["structure_id"], base_amount="1000.00")
    _insert_payable_workdays(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=employee_a_id,
        days=[date(2026, 1, 1)],
        present_days={date(2026, 1, 1)},
    )

    workflow_factory.create_definition_role(
        admin_api,
        request_type_code="PAYRUN_APPROVAL",
        role_code="HR_ADMIN",
        code_prefix="PAYRUN",
    )

    payrun = hr_api.post(
        "/api/v1/payroll/payruns/generate",
        json={
            "calendar_id": setup["calendar_id"],
            "period_key": setup["period_key"],
            "idempotency_key": "k8",
        },
    )
    submitted = hr_api.post(f"/api/v1/payroll/payruns/{payrun['id']}/submit-approval", json={})
    hr_api.post(f"/api/v1/workflow/requests/{submitted['workflow_request_id']}/approve", json={})

    # ------------------------------------------------------------------
    # Act
    # ------------------------------------------------------------------
    hr_api.post(f"/api/v1/payroll/payruns/{payrun['id']}/publish", json={})

    # Second call should be rejected (lock + state guard).
    r2 = hr_api.client.post(
        f"/api/v1/payroll/payruns/{payrun['id']}/publish",
        headers=hr_api.headers,
        json={},
    )
    assert r2.status_code == 409
    assert r2.json()["error"]["code"] == "payroll.payrun.already_published"

    # ------------------------------------------------------------------
    # Assert: no duplicate payslips created
    # ------------------------------------------------------------------
    with db_engine.connect() as conn:
        cnt = conn.execute(
            sa.text(
                """
                SELECT COUNT(*)
                FROM payroll.payslips
                WHERE tenant_id = :tenant_id
                  AND payrun_id = :payrun_id
                """
            ),
            {"tenant_id": tenant.tenant_id, "payrun_id": payrun["id"]},
        ).scalar()
        assert int(cnt or 0) == 1


def test_payrun_export_csv_shape(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # ------------------------------------------------------------------
    # Arrange
    # ------------------------------------------------------------------
    ctx = _setup_payroll_app(client_factory=client_factory, tenant_factory=tenant_factory, actor_factory=actor_factory)
    tenant = ctx["tenant"]
    hr_api: ApiClient = ctx["hr_api"]
    employee_a_id = ctx["employee_a_id"]

    setup = _create_basic_payroll_setup(hr_api)
    _create_compensation(hr_api, employee_id=employee_a_id, structure_id=setup["structure_id"], base_amount="1000.00")
    _insert_payable_workdays(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=employee_a_id,
        days=[date(2026, 1, 1)],
        present_days={date(2026, 1, 1)},
    )

    payrun = hr_api.post(
        "/api/v1/payroll/payruns/generate",
        json={
            "calendar_id": setup["calendar_id"],
            "period_key": setup["period_key"],
            "idempotency_key": "k9",
        },
    )

    # ------------------------------------------------------------------
    # Act
    # ------------------------------------------------------------------
    r = hr_api.raw_get(f"/api/v1/payroll/payruns/{payrun['id']}/export", params={"format": "csv"})

    # ------------------------------------------------------------------
    # Assert
    # ------------------------------------------------------------------
    assert r.status_code == 200
    assert r.headers.get("content-type", "").startswith("text/csv")
    first_line = r.content.decode("utf-8").splitlines()[0]
    assert first_line.startswith("employee_id,employee_code,payable_days,gross_amount")
