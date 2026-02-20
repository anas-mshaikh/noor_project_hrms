from __future__ import annotations

import os
import uuid
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine, text

from tests.helpers.app import make_app
from tests.helpers.http import auth_headers, create_employee, link_user_to_employee, login
from tests.helpers.seed import cleanup, seed_tenant_company, seed_user


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping API integration tests",
)


def _create_workflow_definition_document_verification(client, *, token: str) -> None:
    """
    Configure a deterministic workflow for tests:
    - Single ROLE step assigned to HR_ADMIN
    """

    r = client.post(
        "/api/v1/workflow/definitions",
        headers=auth_headers(token),
        json={
            "request_type_code": "DOCUMENT_VERIFICATION",
            "code": f"DOC_VERIFY_{uuid.uuid4().hex[:6]}",
            "name": "Document verification (HR_ADMIN)",
            "version": 1,
        },
    )
    assert r.status_code == 200, r.text
    definition_id = r.json()["data"]["id"]

    r2 = client.post(
        f"/api/v1/workflow/definitions/{definition_id}/steps",
        headers=auth_headers(token),
        json={"steps": [{"step_index": 0, "assignee_type": "ROLE", "assignee_role_code": "HR_ADMIN"}]},
    )
    assert r2.status_code == 200, r2.text

    r3 = client.post(
        f"/api/v1/workflow/definitions/{definition_id}/activate",
        headers=auth_headers(token),
    )
    assert r3.status_code == 200, r3.text


def test_dms_file_upload_and_download_hr() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-dms-file",
    )
    created_users = [admin["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.dms.router_files",
            )
        )

        token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        payload_bytes = b"hello-dms"
        up = client.post(
            "/api/v1/dms/files",
            headers=auth_headers(token),
            files={"file": ("hello.txt", payload_bytes, "text/plain")},
        )
        assert up.status_code == 200, up.text
        file_id = up.json()["data"]["id"]
        assert up.json()["data"]["status"] == "READY"

        meta = client.get(
            f"/api/v1/dms/files/{file_id}",
            headers=auth_headers(token),
        )
        assert meta.status_code == 200, meta.text
        assert meta.json()["data"]["content_type"] == "text/plain"

        dl = client.get(
            f"/api/v1/dms/files/{file_id}/download",
            headers=auth_headers(token),
        )
        assert dl.status_code == 200
        assert dl.content == payload_bytes
        assert dl.headers.get("content-type", "").startswith("text/plain")
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_dms_file_tenant_isolation() -> None:
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
        email_prefix="admin-dms-a",
    )
    admin_b = seed_user(
        engine,
        tenant_id=tenant_b["tenant_id"],
        company_id=tenant_b["company_id"],
        branch_id=tenant_b["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-dms-b",
    )
    created_users = [admin_a["user_id"], admin_b["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.dms.router_files",
            )
        )

        token_a = login(client, email=admin_a["email"], password=admin_a["password"])["access_token"]
        token_b = login(client, email=admin_b["email"], password=admin_b["password"])["access_token"]

        up = client.post(
            "/api/v1/dms/files",
            headers=auth_headers(token_a),
            files={"file": ("a.txt", b"tenant-a", "text/plain")},
        )
        assert up.status_code == 200, up.text
        file_id = up.json()["data"]["id"]

        # Tenant B cannot read/download tenant A file.
        dl = client.get(
            f"/api/v1/dms/files/{file_id}/download",
            headers=auth_headers(token_b),
        )
        assert dl.status_code == 404
        assert dl.json()["error"]["code"] == "dms.file.not_found"
    finally:
        cleanup(engine, tenant_id=tenant_a["tenant_id"], user_ids=[])
        cleanup(engine, tenant_id=tenant_b["tenant_id"], user_ids=created_users)


def test_employee_document_library_hr_create_and_ess_read() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-docs")
    emp1 = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-docs-1")
    emp2 = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-docs-2")
    created_users = [admin["user_id"], emp1["user_id"], emp2["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.dms.router_files",
                "app.domains.dms.router_document_types",
                "app.domains.dms.router_hr",
                "app.domains.dms.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        emp1_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Doc",
            last_name="Owner",
        )
        link_user_to_employee(client, token=admin_token, employee_id=emp1_id, user_id=emp1["user_id"])

        emp2_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Other",
            last_name="Employee",
        )
        link_user_to_employee(client, token=admin_token, employee_id=emp2_id, user_id=emp2["user_id"])

        # Create a document type.
        dt = client.post(
            "/api/v1/dms/document-types",
            headers=auth_headers(admin_token),
            json={"code": "ID", "name": "National ID", "requires_expiry": True, "is_active": True},
        )
        assert dt.status_code == 200, dt.text

        # Upload a file.
        up = client.post(
            "/api/v1/dms/files",
            headers=auth_headers(admin_token),
            files={"file": ("id.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert up.status_code == 200, up.text
        file_id = up.json()["data"]["id"]

        # HR creates employee document.
        doc = client.post(
            f"/api/v1/hr/employees/{emp1_id}/documents",
            headers=auth_headers(admin_token),
            json={"document_type_code": "ID", "file_id": file_id, "expires_at": "2026-12-31", "notes": "initial"},
        )
        assert doc.status_code == 200, doc.text
        document_id = doc.json()["data"]["id"]

        # Owner can list and fetch.
        emp1_token = login(client, email=emp1["email"], password=emp1["password"])["access_token"]

        lst = client.get("/api/v1/ess/me/documents?limit=50", headers=auth_headers(emp1_token))
        assert lst.status_code == 200, lst.text
        assert any(d["id"] == document_id for d in lst.json()["data"]["items"])

        get1 = client.get(f"/api/v1/ess/me/documents/{document_id}", headers=auth_headers(emp1_token))
        assert get1.status_code == 200, get1.text
        assert get1.json()["data"]["id"] == document_id

        # Other employee cannot fetch (participant-safe 404).
        emp2_token = login(client, email=emp2["email"], password=emp2["password"])["access_token"]
        get2 = client.get(f"/api/v1/ess/me/documents/{document_id}", headers=auth_headers(emp2_token))
        assert get2.status_code == 404, get2.text
        assert get2.json()["error"]["code"] == "dms.document.not_found"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_document_new_version_updates_current() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-doc-v")
    created_users = [admin["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.dms.router_files",
                "app.domains.dms.router_document_types",
                "app.domains.dms.router_documents",
                "app.domains.dms.router_hr",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        # Create employee to own the document.
        emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Ver",
            last_name="One",
        )

        # Type + file + doc v1
        dt = client.post(
            "/api/v1/dms/document-types",
            headers=auth_headers(admin_token),
            json={"code": "CONTRACT", "name": "Contract", "requires_expiry": False, "is_active": True},
        )
        assert dt.status_code == 200, dt.text

        f1 = client.post(
            "/api/v1/dms/files",
            headers=auth_headers(admin_token),
            files={"file": ("v1.txt", b"v1", "text/plain")},
        )
        assert f1.status_code == 200, f1.text
        file1_id = f1.json()["data"]["id"]

        doc = client.post(
            f"/api/v1/hr/employees/{emp_id}/documents",
            headers=auth_headers(admin_token),
            json={"document_type_code": "CONTRACT", "file_id": file1_id, "expires_at": None, "notes": "v1"},
        )
        assert doc.status_code == 200, doc.text
        document_id = doc.json()["data"]["id"]
        current_v1 = doc.json()["data"]["current_version"]["version"]
        assert current_v1 == 1

        # Upload v2 + add version
        f2 = client.post(
            "/api/v1/dms/files",
            headers=auth_headers(admin_token),
            files={"file": ("v2.txt", b"v2", "text/plain")},
        )
        assert f2.status_code == 200, f2.text
        file2_id = f2.json()["data"]["id"]

        v2 = client.post(
            f"/api/v1/dms/documents/{document_id}/versions",
            headers=auth_headers(admin_token),
            json={"file_id": file2_id, "notes": "v2"},
        )
        assert v2.status_code == 200, v2.text
        assert v2.json()["data"]["current_version"]["version"] == 2
        assert v2.json()["data"]["current_version"]["file_id"] == file2_id

        # Audit exists for new version.
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT action
                    FROM audit.audit_log
                    WHERE tenant_id = :tenant_id
                      AND entity_type = 'dms.document'
                      AND entity_id = :entity_id
                      AND action = 'dms.document.new_version'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "entity_id": document_id},
            ).fetchone()
            assert row is not None
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_document_verification_workflow_approved() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-doc-verify")
    hr_approver = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="HR_ADMIN", email_prefix="hr-approver")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-doc-verify")
    created_users = [admin["user_id"], hr_approver["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.workflow.router",
                "app.domains.notifications.router",
                "app.domains.dms.router_files",
                "app.domains.dms.router_document_types",
                "app.domains.dms.router_documents",
                "app.domains.dms.router_hr",
                "app.domains.dms.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        # Workflow engine requires requester to be linked to an employee (even for ROLE steps).
        admin_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"A{uuid.uuid4().hex[:6].upper()}",
            first_name="Admin",
            last_name="Submitter",
        )
        link_user_to_employee(client, token=admin_token, employee_id=admin_emp_id, user_id=admin["user_id"])

        employee_emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Owner",
            last_name="Employee",
        )
        link_user_to_employee(client, token=admin_token, employee_id=employee_emp_id, user_id=employee_user["user_id"])

        _create_workflow_definition_document_verification(client, token=admin_token)

        # Document type + file + document
        dt = client.post(
            "/api/v1/dms/document-types",
            headers=auth_headers(admin_token),
            json={"code": "PASSPORT", "name": "Passport", "requires_expiry": True, "is_active": True},
        )
        assert dt.status_code == 200, dt.text

        up = client.post(
            "/api/v1/dms/files",
            headers=auth_headers(admin_token),
            files={"file": ("passport.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert up.status_code == 200, up.text
        file_id = up.json()["data"]["id"]

        doc = client.post(
            f"/api/v1/hr/employees/{employee_emp_id}/documents",
            headers=auth_headers(admin_token),
            json={"document_type_code": "PASSPORT", "file_id": file_id, "expires_at": "2026-12-31", "notes": "v1"},
        )
        assert doc.status_code == 200, doc.text
        document_id = doc.json()["data"]["id"]

        # Submit verification request (workflow).
        vr = client.post(
            f"/api/v1/dms/documents/{document_id}/verify-request",
            headers=auth_headers(admin_token),
        )
        assert vr.status_code == 200, vr.text
        wf_request_id = vr.json()["data"]["workflow_request_id"]

        # Approver approves via workflow endpoint.
        approver_token = login(client, email=hr_approver["email"], password=hr_approver["password"])["access_token"]
        appr = client.post(
            f"/api/v1/workflow/requests/{wf_request_id}/approve",
            headers=auth_headers(approver_token),
            json={"comment": "verified"},
        )
        assert appr.status_code == 200, appr.text

        # Document becomes VERIFIED (visible to owner via ESS endpoint).
        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        get_doc = client.get(f"/api/v1/ess/me/documents/{document_id}", headers=auth_headers(emp_token))
        assert get_doc.status_code == 200, get_doc.text
        assert get_doc.json()["data"]["status"] == "VERIFIED"

        # Deliver notifications (outbox -> notifications).
        from app.worker.notification_worker import consume_once

        res = consume_once(limit=50)
        assert res.failed == 0

        notif = client.get("/api/v1/notifications?unread_only=1&limit=50", headers=auth_headers(emp_token))
        assert notif.status_code == 200, notif.text
        assert any(n["type"] == "dms.document.verified" for n in notif.json()["data"]["items"])

        # Audit exists for verification.
        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT action
                    FROM audit.audit_log
                    WHERE tenant_id = :tenant_id
                      AND entity_type = 'dms.document'
                      AND entity_id = :entity_id
                      AND action = 'dms.document.verified'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "entity_id": document_id},
            ).fetchone()
            assert row is not None
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_expiry_worker_emits_notifications_idempotent() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="ADMIN", email_prefix="admin-expiry")
    employee_user = seed_user(engine, tenant_id=tenant["tenant_id"], company_id=tenant["company_id"], branch_id=tenant["branch_id"], role_code="EMPLOYEE", email_prefix="emp-expiry")
    created_users = [admin["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.notifications.router",
                "app.domains.dms.router_files",
                "app.domains.dms.router_document_types",
                "app.domains.dms.router_hr",
                "app.domains.dms.router_expiry",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Expiry",
            last_name="Owner",
        )
        link_user_to_employee(client, token=admin_token, employee_id=emp_id, user_id=employee_user["user_id"])

        # Document type
        dt = client.post(
            "/api/v1/dms/document-types",
            headers=auth_headers(admin_token),
            json={"code": "VISA", "name": "Visa", "requires_expiry": True, "is_active": True},
        )
        assert dt.status_code == 200, dt.text

        # Expiry rule: notify 7 days before.
        rule = client.post(
            "/api/v1/dms/expiry/rules",
            headers=auth_headers(admin_token),
            json={"document_type_code": "VISA", "days_before": 7, "is_active": True},
        )
        assert rule.status_code == 200, rule.text

        # Create document expiring in 7 days (notify today).
        up = client.post(
            "/api/v1/dms/files",
            headers=auth_headers(admin_token),
            files={"file": ("visa.pdf", b"%PDF-1.4", "application/pdf")},
        )
        assert up.status_code == 200, up.text
        file_id = up.json()["data"]["id"]

        today = date.today()
        expires_on = today + timedelta(days=7)
        doc = client.post(
            f"/api/v1/hr/employees/{emp_id}/documents",
            headers=auth_headers(admin_token),
            json={"document_type_code": "VISA", "file_id": file_id, "expires_at": str(expires_on), "notes": "v1"},
        )
        assert doc.status_code == 200, doc.text
        document_id = doc.json()["data"]["id"]

        # Run expiry worker twice; expect idempotent inserts.
        from app.worker.dms_expiry_worker import run_once

        run_once(lookahead_days=60, run_date=today)
        run_once(lookahead_days=60, run_date=today)

        with engine.connect() as conn:
            ev_count = int(
                conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM dms.expiry_events
                        WHERE tenant_id = :tenant_id
                          AND document_id = :document_id
                          AND notify_on_date = :today
                          AND event_type = 'EXPIRING'
                        """
                    ),
                    {"tenant_id": tenant["tenant_id"], "document_id": document_id, "today": today},
                ).scalar()
                or 0
            )
            assert ev_count == 1

            outbox_count = int(
                conn.execute(
                    text(
                        """
                        SELECT count(*)
                        FROM workflow.notification_outbox
                        WHERE tenant_id = :tenant_id
                          AND recipient_user_id = :user_id
                          AND template_code = 'dms.document.expiring'
                          AND payload->>'entity_id' = :document_id
                        """
                    ),
                    {"tenant_id": tenant["tenant_id"], "user_id": employee_user["user_id"], "document_id": document_id},
                ).scalar()
                or 0
            )
            assert outbox_count == 1

        # Deliver notification and assert in notifications inbox.
        from app.worker.notification_worker import consume_once

        consume_once(limit=50)

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])["access_token"]
        notif = client.get("/api/v1/notifications?unread_only=1&limit=50", headers=auth_headers(emp_token))
        assert notif.status_code == 200, notif.text
        assert any(n["type"] == "dms.document.expiring" for n in notif.json()["data"]["items"])
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)
