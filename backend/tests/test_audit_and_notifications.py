from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text

from tests.helpers.app import make_app
from tests.helpers.http import create_employee, login
from tests.helpers.seed import cleanup, seed_tenant_company, seed_user


pytestmark = pytest.mark.skipif(
    not os.getenv("DATABASE_URL"),
    reason="DATABASE_URL not set; skipping API integration tests",
)


def test_audit_row_created_on_hr_employee_patch() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-audit",
    )
    created_users = [admin["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(make_app("app.auth.router", "app.domains.hr_core.router_hr"))
        token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        employee_id = create_employee(
            client,
            token=token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Alice",
            last_name="Audit",
        )

        corr_id = f"test-corr-{uuid.uuid4().hex[:8]}"
        patch = client.patch(
            f"/api/v1/hr/employees/{employee_id}",
            headers={"Authorization": f"Bearer {token}", "X-Correlation-Id": corr_id},
            json={"person": {"phone": "+15551234567"}},
        )
        assert patch.status_code == 200, patch.text

        with engine.connect() as conn:
            row = conn.execute(
                text(
                    """
                    SELECT tenant_id, actor_user_id, action, entity_id, correlation_id
                    FROM audit.audit_log
                    WHERE tenant_id = :tenant_id
                      AND action = 'hr.employee.patch'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant["tenant_id"]},
            ).fetchone()
            assert row is not None
            assert str(row.actor_user_id) == admin["user_id"]
            assert str(row.entity_id) == employee_id
            assert row.correlation_id == corr_id
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_notifications_outbox_to_api_self_only() -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-notif",
    )
    target = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="target-notif",
    )
    outsider = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="outsider-notif",
    )
    created_users = [admin["user_id"], target["user_id"], outsider["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.iam.router",
                "app.domains.notifications.router",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])["access_token"]

        ar = client.post(
            f"/api/v1/iam/users/{target['user_id']}/roles",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"role_code": "MANAGER", "branch_id": tenant["branch_id"]},
        )
        assert ar.status_code == 200, ar.text

        with engine.connect() as conn:
            outbox_id = conn.execute(
                text(
                    """
                    SELECT id
                    FROM workflow.notification_outbox
                    WHERE tenant_id = :tenant_id
                      AND recipient_user_id = :user_id
                      AND template_code = 'ROLE_ASSIGNED'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "user_id": target["user_id"]},
            ).scalar()
            assert outbox_id is not None

        from app.worker.notification_worker import consume_once

        res = consume_once(limit=10)
        assert res.failed == 0
        assert res.processed >= 1

        target_token = login(client, email=target["email"], password=target["password"])["access_token"]
        outsider_token = login(client, email=outsider["email"], password=outsider["password"])["access_token"]

        lst = client.get(
            "/api/v1/notifications?unread_only=1&limit=50",
            headers={"Authorization": f"Bearer {target_token}"},
        )
        assert lst.status_code == 200, lst.text
        items = lst.json()["data"]["items"]
        assert len(items) >= 1
        nid = items[0]["id"]

        count = client.get(
            "/api/v1/notifications/unread-count",
            headers={"Authorization": f"Bearer {target_token}"},
        )
        assert count.status_code == 200, count.text
        assert int(count.json()["data"]["unread_count"]) >= 1

        # Outsider cannot read/modify target's notifications.
        outsider_read = client.post(
            f"/api/v1/notifications/{nid}/read",
            headers={"Authorization": f"Bearer {outsider_token}"},
        )
        assert outsider_read.status_code == 404, outsider_read.text

        mark = client.post(
            f"/api/v1/notifications/{nid}/read",
            headers={"Authorization": f"Bearer {target_token}"},
        )
        assert mark.status_code == 200, mark.text

        count2 = client.get(
            "/api/v1/notifications/unread-count",
            headers={"Authorization": f"Bearer {target_token}"},
        )
        assert count2.status_code == 200, count2.text
        assert int(count2.json()["data"]["unread_count"]) == 0
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)

