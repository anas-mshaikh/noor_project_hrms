from __future__ import annotations

import os
import uuid
from datetime import date

import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine

from tests.support.httpx_client import expect_ok, live_client


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.golden,
    pytest.mark.e2e,
    pytest.mark.api,
    pytest.mark.tenant,
    pytest.mark.rbac,
    pytest.mark.skipif(
        not os.getenv("BASE_URL") or not os.getenv("DATABASE_URL"),
        reason="BASE_URL and DATABASE_URL are required for golden API journeys",
    ),
]


def _engine():
    return create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


async def _login(client, *, email: str, password: str) -> dict:
    response = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return expect_ok(response)


async def _create_user(client, *, token: str, email_prefix: str) -> dict:
    email = f"{email_prefix}+{uuid.uuid4().hex[:10]}@example.com"
    response = await client.post(
        "/api/v1/iam/users",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": email, "password": "StrongPass123", "status": "ACTIVE"},
    )
    data = expect_ok(response)
    return {"id": data["id"], "email": email, "password": "StrongPass123"}


async def _assign_role(
    client,
    *,
    token: str,
    user_id: str,
    role_code: str,
    tenant_id: str,
    company_id: str,
    branch_id: str,
) -> None:
    response = await client.post(
        f"/api/v1/iam/users/{user_id}/roles",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "role_code": role_code,
            "tenant_id": tenant_id,
            "company_id": company_id,
            "branch_id": branch_id,
        },
    )
    if response.status_code == 409:
        body = response.json()
        assert body == {
            "ok": False,
            "error": {
                "code": "iam.user_role.duplicate",
                "message": "Role assignment already exists",
                "correlation_id": body["error"]["correlation_id"],
            },
        }
        return

    expect_ok(response)


async def _create_employee(
    client, *, token: str, company_id: str, branch_id: str, first_name: str
) -> str:
    response = await client.post(
        "/api/v1/hr/employees",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "person": {"first_name": first_name, "last_name": "Journey", "address": {}},
            "employee": {
                "company_id": company_id,
                "employee_code": f"E{uuid.uuid4().hex[:6].upper()}",
                "status": "ACTIVE",
            },
            "employment": {"start_date": "2026-01-01", "branch_id": branch_id, "is_primary": True},
        },
    )
    return expect_ok(response)["employee"]["id"]


async def _link_user(client, *, token: str, employee_id: str, user_id: str) -> None:
    response = await client.post(
        f"/api/v1/hr/employees/{employee_id}/link-user",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": user_id},
    )
    expect_ok(response)


async def _create_role_workflow(
    client, *, token: str, request_type_code: str, role_code: str, code_prefix: str
) -> str:
    definition = await client.post(
        "/api/v1/workflow/definitions",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "request_type_code": request_type_code,
            "code": f"{code_prefix}_{uuid.uuid4().hex[:6]}",
            "name": f"{request_type_code} ({role_code})",
            "version": 1,
        },
    )
    definition_id = expect_ok(definition)["id"]

    steps = await client.post(
        f"/api/v1/workflow/definitions/{definition_id}/steps",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "steps": [{"step_index": 0, "assignee_type": "ROLE", "assignee_role_code": role_code}]
        },
    )
    expect_ok(steps)

    activate = await client.post(
        f"/api/v1/workflow/definitions/{definition_id}/activate",
        headers={"Authorization": f"Bearer {token}"},
        json={},
    )
    expect_ok(activate)
    return definition_id


def _insert_payable_workday(
    *, tenant_id: str, branch_id: str, employee_id: str, day_value: date
) -> None:
    with _engine().begin() as conn:
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
                  'PRESENT',
                  480,
                  480,
                  480
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
                "day": day_value,
            },
        )


async def test_bootstrap_to_dms_and_payroll_golden_journey() -> None:
    base_url = os.environ["BASE_URL"]

    async with live_client(base_url=base_url) as client:
        bootstrap = await client.post(
            "/api/v1/bootstrap",
            json={
                "tenant_name": "Golden Tenant",
                "company_name": "Golden Company",
                "branch_name": "HQ",
                "branch_code": "HQ",
                "timezone": "Asia/Riyadh",
                "currency_code": "SAR",
                "admin_email": f"admin+{uuid.uuid4().hex[:8]}@example.com",
                "admin_password": "StrongPass123",
            },
        )
        admin_data = expect_ok(bootstrap)
        admin_token = admin_data["access_token"]
        tenant_id = admin_data["scope"]["tenant_id"]
        company_id = admin_data["scope"]["company_id"]
        branch_id = admin_data["scope"]["branch_id"]

        hr_admin_user = await _create_user(
            client, token=admin_token, email_prefix="golden-hr-admin"
        )
        employee_user = await _create_user(
            client, token=admin_token, email_prefix="golden-employee"
        )

        await _assign_role(
            client,
            token=admin_token,
            user_id=hr_admin_user["id"],
            role_code="HR_ADMIN",
            tenant_id=tenant_id,
            company_id=company_id,
            branch_id=branch_id,
        )
        await _assign_role(
            client,
            token=admin_token,
            user_id=employee_user["id"],
            role_code="EMPLOYEE",
            tenant_id=tenant_id,
            company_id=company_id,
            branch_id=branch_id,
        )

        hr_admin_token = (
            await _login(client, email=hr_admin_user["email"], password=hr_admin_user["password"])
        )["access_token"]
        employee_token = (
            await _login(client, email=employee_user["email"], password=employee_user["password"])
        )["access_token"]

        payroll_admin_employee_id = await _create_employee(
            client,
            token=admin_token,
            company_id=company_id,
            branch_id=branch_id,
            first_name="PayrollAdmin",
        )
        await _link_user(
            client,
            token=admin_token,
            employee_id=payroll_admin_employee_id,
            user_id=hr_admin_user["id"],
        )

        employee_id = await _create_employee(
            client,
            token=admin_token,
            company_id=company_id,
            branch_id=branch_id,
            first_name="Employee",
        )
        await _link_user(
            client, token=admin_token, employee_id=employee_id, user_id=employee_user["id"]
        )

        me = await client.get(
            "/api/v1/ess/me/profile", headers={"Authorization": f"Bearer {employee_token}"}
        )
        assert expect_ok(me)["employee"]["id"] == employee_id

        await _create_role_workflow(
            client,
            token=admin_token,
            request_type_code="DOCUMENT_VERIFICATION",
            role_code="HR_ADMIN",
            code_prefix="DOCVERIFY",
        )
        await _create_role_workflow(
            client,
            token=admin_token,
            request_type_code="PAYRUN_APPROVAL",
            role_code="HR_ADMIN",
            code_prefix="PAYRUN",
        )

        doc_type = await client.post(
            "/api/v1/dms/document-types",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "code": "PASSPORT",
                "name": "Passport",
                "requires_expiry": True,
                "is_active": True,
            },
        )
        expect_ok(doc_type)

        upload = await client.post(
            "/api/v1/dms/files",
            headers={"Authorization": f"Bearer {admin_token}"},
            files={"file": ("passport.pdf", b"%PDF-1.4 golden", "application/pdf")},
        )
        file_id = expect_ok(upload)["id"]

        doc = await client.post(
            f"/api/v1/hr/employees/{employee_id}/documents",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "document_type_code": "PASSPORT",
                "file_id": file_id,
                "expires_at": "2026-12-31",
                "notes": "golden",
            },
        )
        document_id = expect_ok(doc)["id"]

        verify_request = await client.post(
            f"/api/v1/dms/documents/{document_id}/verify-request",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            json={},
        )
        workflow_request_id = expect_ok(verify_request)["workflow_request_id"]

        approve_doc = await client.post(
            f"/api/v1/workflow/requests/{workflow_request_id}/approve",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            json={},
        )
        expect_ok(approve_doc)

        my_doc = await client.get(
            f"/api/v1/ess/me/documents/{document_id}",
            headers={"Authorization": f"Bearer {employee_token}"},
        )
        assert expect_ok(my_doc)["status"] == "VERIFIED"

        calendar = await client.post(
            "/api/v1/payroll/calendars",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            json={
                "code": f"CAL{uuid.uuid4().hex[:4]}",
                "name": "Monthly",
                "currency_code": "SAR",
                "timezone": "UTC",
            },
        )
        calendar_id = expect_ok(calendar)["id"]

        period = await client.post(
            f"/api/v1/payroll/calendars/{calendar_id}/periods",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            json={"period_key": "2026-01", "start_date": "2026-01-01", "end_date": "2026-01-31"},
        )
        expect_ok(period)

        component = await client.post(
            "/api/v1/payroll/components",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            json={
                "code": f"BASIC{uuid.uuid4().hex[:4]}",
                "name": "Basic Salary",
                "component_type": "EARNING",
                "calc_mode": "FIXED",
                "default_amount": "1000.00",
                "is_taxable": False,
                "is_active": True,
            },
        )
        component_id = expect_ok(component)["id"]

        structure = await client.post(
            "/api/v1/payroll/salary-structures",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            json={"code": f"SS{uuid.uuid4().hex[:4]}", "name": "Base Only", "is_active": True},
        )
        structure_id = expect_ok(structure)["id"]

        structure_line = await client.post(
            f"/api/v1/payroll/salary-structures/{structure_id}/lines",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            json={"component_id": component_id, "sort_order": 0, "amount_override": "1000.00"},
        )
        expect_ok(structure_line)

        compensation = await client.post(
            f"/api/v1/payroll/employees/{employee_id}/compensation",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            json={
                "currency_code": "SAR",
                "salary_structure_id": structure_id,
                "base_amount": "1000.00",
                "effective_from": "2026-01-01",
                "effective_to": None,
            },
        )
        expect_ok(compensation)

        _insert_payable_workday(
            tenant_id=tenant_id,
            branch_id=branch_id,
            employee_id=employee_id,
            day_value=date(2026, 1, 1),
        )

        payrun = await client.post(
            "/api/v1/payroll/payruns/generate",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            json={
                "calendar_id": calendar_id,
                "period_key": "2026-01",
                "idempotency_key": "golden-k1",
            },
        )
        payrun_id = expect_ok(payrun)["id"]

        submitted = await client.post(
            f"/api/v1/payroll/payruns/{payrun_id}/submit-approval",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            json={},
        )
        payrun_request_id = expect_ok(submitted)["workflow_request_id"]

        approve_payrun = await client.post(
            f"/api/v1/workflow/requests/{payrun_request_id}/approve",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            json={},
        )
        expect_ok(approve_payrun)

        published = await client.post(
            f"/api/v1/payroll/payruns/{payrun_id}/publish",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            json={},
        )
        assert int(expect_ok(published)["published_count"]) >= 1

        export = await client.get(
            f"/api/v1/payroll/payruns/{payrun_id}/export",
            headers={"Authorization": f"Bearer {hr_admin_token}"},
            params={"format": "csv"},
        )
        assert export.status_code == 200
        assert export.content
        assert export.headers.get("content-type", "").startswith("text/csv")

        payslips = await client.get(
            "/api/v1/ess/me/payslips",
            headers={"Authorization": f"Bearer {employee_token}"},
            params={"year": 2026},
        )
        payslip_items = expect_ok(payslips)["items"]
        assert payslip_items
        payslip_id = payslip_items[0]["id"]

        download = await client.get(
            f"/api/v1/ess/me/payslips/{payslip_id}/download",
            headers={"Authorization": f"Bearer {employee_token}"},
        )
        assert download.status_code == 200
        assert download.content
        assert download.headers.get("content-type", "").startswith("application/json")
