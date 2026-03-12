from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from tests.helpers.app import make_app
from tests.helpers.seed import cleanup, role_id, seed_tenant_company, seed_user
from tests.support.httpx_client import asgi_client, expect_error, expect_ok


pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.contract,
    pytest.mark.api,
    pytest.mark.tenant,
    pytest.mark.rbac,
    pytest.mark.skipif(
        not os.getenv("DATABASE_URL"),
        reason="DATABASE_URL not set; skipping API integration tests",
    ),
]


def _engine():
    return create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)


async def _login(client, *, email: str, password: str, tenant_id: str | None = None) -> dict:
    headers = {"X-Tenant-Id": tenant_id} if tenant_id is not None else None
    response = await client.post(
        "/api/v1/auth/login",
        headers=headers,
        json={"email": email, "password": password},
    )
    return expect_ok(response)


async def _create_employee(client, *, token: str, company_id: str, branch_id: str, first_name: str) -> str:
    response = await client.post(
        "/api/v1/hr/employees",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "person": {"first_name": first_name, "last_name": "User", "address": {}},
            "employee": {"company_id": company_id, "employee_code": f"E{uuid.uuid4().hex[:6].upper()}", "status": "ACTIVE"},
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


async def test_scope_errors_are_fail_closed_and_stable() -> None:
    engine = _engine()
    tenant_a = seed_tenant_company(engine, with_second_branch=True)
    tenant_b = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant_a["tenant_id"],
        company_id=tenant_a["company_id"],
        branch_id=tenant_a["branch_id"],
        role_code="ADMIN",
        email_prefix="multi-tenant-admin",
    )

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO iam.user_roles (user_id, tenant_id, company_id, branch_id, role_id)
                VALUES (:user_id, :tenant_id, :company_id, :branch_id, :role_id)
                """
            ),
            {
                "user_id": admin["user_id"],
                "tenant_id": tenant_b["tenant_id"],
                "company_id": tenant_b["company_id"],
                "branch_id": tenant_b["branch_id"],
                "role_id": role_id(conn, "ADMIN"),
            },
        )

    app = make_app("app.auth.router", "app.api.v1.cameras")

    try:
        async with asgi_client(app) as client:
            token = (
                await _login(
                    client,
                    email=admin["email"],
                    password=admin["password"],
                    tenant_id=tenant_a["tenant_id"],
                )
            )["access_token"]
            auth = {"Authorization": f"Bearer {token}"}

            missing_tenant = await client.get("/api/v1/auth/me", headers=auth)
            assert expect_error(missing_tenant)["code"] == "iam.scope.tenant_required"

            invalid_company = await client.get(
                "/api/v1/auth/me",
                headers={
                    **auth,
                    "X-Tenant-Id": tenant_a["tenant_id"],
                    "X-Company-Id": str(uuid.uuid4()),
                },
            )
            assert expect_error(invalid_company)["code"] == "iam.scope.invalid_company"

            forbidden_tenant = await client.get(
                "/api/v1/auth/me",
                headers={**auth, "X-Tenant-Id": str(uuid.uuid4())},
            )
            assert expect_error(forbidden_tenant)["code"] == "iam.scope.forbidden_tenant"

            mismatch = await client.get(
                f"/api/v1/branches/{tenant_a['branch_id']}/cameras",
                headers={
                    **auth,
                    "X-Tenant-Id": tenant_a["tenant_id"],
                    "X-Company-Id": tenant_a["company_id"],
                    "X-Branch-Id": tenant_a["branch2_id"],
                },
            )
            assert expect_error(mismatch)["code"] == "iam.scope.mismatch"
    finally:
        cleanup(engine, tenant_id=tenant_a["tenant_id"], user_ids=[])
        cleanup(engine, tenant_id=tenant_b["tenant_id"], user_ids=[admin["user_id"]])


async def test_ess_dms_and_payslips_remain_participant_safe() -> None:
    engine = _engine()
    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="ps-admin")
    owner = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="ps-owner")
    other = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="ps-other")

    app = make_app(
        "app.auth.router",
        "app.domains.hr_core.router_hr",
        "app.domains.dms.router_files",
        "app.domains.dms.router_document_types",
        "app.domains.dms.router_hr",
        "app.domains.dms.router_ess",
        "app.domains.payroll.router_ess",
    )

    try:
        async with asgi_client(app) as client:
            admin_token = (await _login(client, email=admin["email"], password=admin["password"]))["access_token"]
            owner_token = (await _login(client, email=owner["email"], password=owner["password"]))["access_token"]
            other_token = (await _login(client, email=other["email"], password=other["password"]))["access_token"]

            owner_employee_id = await _create_employee(
                client,
                token=admin_token,
                company_id=tenant["company_id"],
                branch_id=tenant["branch_id"],
                first_name="Owner",
            )
            await _link_user(client, token=admin_token, employee_id=owner_employee_id, user_id=owner["user_id"])

            other_employee_id = await _create_employee(
                client,
                token=admin_token,
                company_id=tenant["company_id"],
                branch_id=tenant["branch_id"],
                first_name="Other",
            )
            await _link_user(client, token=admin_token, employee_id=other_employee_id, user_id=other["user_id"])

            create_type = await client.post(
                "/api/v1/dms/document-types",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"code": "ID", "name": "National ID", "requires_expiry": True, "is_active": True},
            )
            expect_ok(create_type)

            upload = await client.post(
                "/api/v1/dms/files",
                headers={"Authorization": f"Bearer {admin_token}"},
                files={"file": ("id.pdf", b"%PDF-1.4", "application/pdf")},
            )
            file_id = expect_ok(upload)["id"]

            created_doc = await client.post(
                f"/api/v1/hr/employees/{owner_employee_id}/documents",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"document_type_code": "ID", "file_id": file_id, "expires_at": "2026-12-31", "notes": "initial"},
            )
            document_id = expect_ok(created_doc)["id"]

            not_my_doc = await client.get(
                f"/api/v1/ess/me/documents/{document_id}",
                headers={"Authorization": f"Bearer {other_token}"},
            )
            assert expect_error(not_my_doc)["code"] == "dms.document.not_found"

            missing_payslip = await client.get(
                f"/api/v1/ess/me/payslips/{uuid.uuid4()}",
                headers={"Authorization": f"Bearer {owner_token}"},
            )
            assert expect_error(missing_payslip)["code"] == "payroll.payslip.not_found"

            missing_payslip_download = await client.get(
                f"/api/v1/ess/me/payslips/{uuid.uuid4()}/download",
                headers={"Authorization": f"Bearer {other_token}"},
            )
            assert expect_error(missing_payslip_download)["code"] == "payroll.payslip.not_found"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=[admin["user_id"], owner["user_id"], other["user_id"]])
