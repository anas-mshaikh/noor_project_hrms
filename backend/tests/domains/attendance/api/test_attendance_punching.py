from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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


def _branch_tz(engine, *, tenant_id: str, branch_id: str) -> ZoneInfo:
    with engine.connect() as conn:
        tz_name = conn.execute(
            text(
                """
                SELECT timezone
                FROM tenancy.branches
                WHERE id = :branch_id
                  AND tenant_id = :tenant_id
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id},
        ).scalar()
    return ZoneInfo(str(tz_name or "UTC"))


def test_punch_in_out_happy_path_creates_daily_minutes(monkeypatch) -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-punch",
    )
    employee_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-punch",
    )
    created_users = [admin["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.attendance.router_ess",
                "app.domains.attendance.router_admin",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Punch",
            last_name="User",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=emp_id,
            user_id=employee_user["user_id"],
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])[
            "access_token"
        ]

        # Patch the punching clock so minute math is deterministic.
        from app.domains.attendance import service_punching

        start = datetime(2026, 2, 20, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 2, 20, 10, 30, tzinfo=timezone.utc)
        now = {"ts": start}

        def _fake_now() -> datetime:
            return now["ts"]

        monkeypatch.setattr(service_punching, "utcnow", _fake_now)

        # Arrange/Act: punch in then punch out.
        now["ts"] = start
        r1 = client.post("/api/v1/attendance/me/punch-in", headers=_auth(emp_token), json={})
        assert r1.status_code == 200, r1.text
        assert r1.json()["data"]["is_punched_in"] is True

        now["ts"] = end
        r2 = client.post("/api/v1/attendance/me/punch-out", headers=_auth(emp_token), json={})
        assert r2.status_code == 200, r2.text
        assert r2.json()["data"]["is_punched_in"] is False

        tz = _branch_tz(engine, tenant_id=tenant["tenant_id"], branch_id=tenant["branch_id"])
        business_day = start.astimezone(tz).date()

        # Assert: one CLOSED session with computed minutes.
        with engine.connect() as conn:
            s = conn.execute(
                text(
                    """
                    SELECT status, minutes
                    FROM attendance.work_sessions
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                    ORDER BY created_at ASC, id ASC
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "employee_id": emp_id},
            ).first()
            assert s is not None
            assert str(s[0]) == "CLOSED"
            assert int(s[1]) == 90

            d = conn.execute(
                text(
                    """
                    SELECT total_minutes, has_open_session
                    FROM attendance.attendance_daily
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                      AND business_date = :day
                    """
                ),
                {
                    "tenant_id": tenant["tenant_id"],
                    "employee_id": emp_id,
                    "day": business_day,
                },
            ).first()
            assert d is not None
            assert int(d[0] or 0) == 90
            assert bool(d[1]) is False

        # Assert punch-state returns base/effective minutes.
        st = client.get("/api/v1/attendance/me/punch-state", headers=_auth(emp_token))
        assert st.status_code == 200, st.text
        assert int(st.json()["data"]["base_minutes_today"]) >= 0
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_punch_in_twice_returns_already_in(monkeypatch) -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-punch2",
    )
    employee_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-punch2",
    )
    created_users = [admin["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.attendance.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Punch",
            last_name="User",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=emp_id,
            user_id=employee_user["user_id"],
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])[
            "access_token"
        ]

        from app.domains.attendance import service_punching

        now = {"ts": datetime(2026, 2, 20, 9, 0, tzinfo=timezone.utc)}

        def _fake_now() -> datetime:
            return now["ts"]

        monkeypatch.setattr(service_punching, "utcnow", _fake_now)

        r1 = client.post("/api/v1/attendance/me/punch-in", headers=_auth(emp_token), json={})
        assert r1.status_code == 200, r1.text

        r2 = client.post("/api/v1/attendance/me/punch-in", headers=_auth(emp_token), json={})
        assert r2.status_code == 409, r2.text
        assert r2.json()["error"]["code"] == "attendance.punch.already_in"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_punch_out_without_in_returns_not_in(monkeypatch) -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-punch3",
    )
    employee_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-punch3",
    )
    created_users = [admin["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.attendance.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Punch",
            last_name="User",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=emp_id,
            user_id=employee_user["user_id"],
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])[
            "access_token"
        ]

        from app.domains.attendance import service_punching

        now = {"ts": datetime(2026, 2, 20, 9, 0, tzinfo=timezone.utc)}

        def _fake_now() -> datetime:
            return now["ts"]

        monkeypatch.setattr(service_punching, "utcnow", _fake_now)

        r = client.post("/api/v1/attendance/me/punch-out", headers=_auth(emp_token), json={})
        assert r.status_code == 409, r.text
        assert r.json()["error"]["code"] == "attendance.punch.not_in"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_punch_disabled_by_branch_setting(monkeypatch) -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-punch4",
    )
    employee_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-punch4",
    )
    created_users = [admin["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.attendance.router_ess",
                "app.domains.attendance.router_admin",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        # Disable punching for the branch.
        rset = client.put(
            f"/api/v1/attendance/punch-settings?branch_id={tenant['branch_id']}",
            headers=_auth(admin_token),
            json={"is_enabled": False},
        )
        assert rset.status_code == 200, rset.text
        assert rset.json()["data"]["is_enabled"] is False

        emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Punch",
            last_name="User",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=emp_id,
            user_id=employee_user["user_id"],
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])[
            "access_token"
        ]

        from app.domains.attendance import service_punching

        now = {"ts": datetime(2026, 2, 20, 9, 0, tzinfo=timezone.utc)}

        def _fake_now() -> datetime:
            return now["ts"]

        monkeypatch.setattr(service_punching, "utcnow", _fake_now)

        r = client.post("/api/v1/attendance/me/punch-in", headers=_auth(emp_token), json={})
        assert r.status_code == 409, r.text
        assert r.json()["error"]["code"] == "attendance.punch.disabled"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_leave_conflict_blocks_punch_in(monkeypatch) -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-punch5",
    )
    employee_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-punch5",
    )
    created_users = [admin["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.attendance.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Punch",
            last_name="User",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=emp_id,
            user_id=employee_user["user_id"],
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])[
            "access_token"
        ]

        from app.domains.attendance import service_punching

        start = datetime(2026, 2, 20, 9, 0, tzinfo=timezone.utc)
        now = {"ts": start}

        def _fake_now() -> datetime:
            return now["ts"]

        monkeypatch.setattr(service_punching, "utcnow", _fake_now)

        tz = _branch_tz(engine, tenant_id=tenant["tenant_id"], branch_id=tenant["branch_id"])
        business_day = start.astimezone(tz).date()

        # Insert an ON_LEAVE override for the day.
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO attendance.day_overrides (
                      tenant_id, employee_id, branch_id, day,
                      status, source_type, source_id, override_kind
                    ) VALUES (
                      :tenant_id, :employee_id, :branch_id, :day,
                      'ON_LEAVE', 'LEAVE_REQUEST', :source_id, 'LEAVE'
                    )
                    """
                ),
                {
                    "tenant_id": tenant["tenant_id"],
                    "employee_id": emp_id,
                    "branch_id": tenant["branch_id"],
                    "day": business_day,
                    "source_id": str(uuid.uuid4()),
                },
            )

        r = client.post("/api/v1/attendance/me/punch-in", headers=_auth(emp_token), json={})
        assert r.status_code == 409, r.text
        assert r.json()["error"]["code"] == "attendance.punch.conflict.leave"
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_correction_override_minutes_effective_minutes(monkeypatch) -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-punch6",
    )
    employee_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-punch6",
    )
    created_users = [admin["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.attendance.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Punch",
            last_name="User",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=emp_id,
            user_id=employee_user["user_id"],
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])[
            "access_token"
        ]

        from app.domains.attendance import service_punching

        start = datetime(2026, 2, 20, 9, 0, tzinfo=timezone.utc)
        end = datetime(2026, 2, 20, 11, 0, tzinfo=timezone.utc)
        now = {"ts": start}

        def _fake_now() -> datetime:
            return now["ts"]

        monkeypatch.setattr(service_punching, "utcnow", _fake_now)

        # Create base minutes via punch in/out.
        now["ts"] = start
        r1 = client.post("/api/v1/attendance/me/punch-in", headers=_auth(emp_token), json={})
        assert r1.status_code == 200, r1.text
        now["ts"] = end
        r2 = client.post("/api/v1/attendance/me/punch-out", headers=_auth(emp_token), json={})
        assert r2.status_code == 200, r2.text

        tz = _branch_tz(engine, tenant_id=tenant["tenant_id"], branch_id=tenant["branch_id"])
        business_day = start.astimezone(tz).date()

        # Insert correction override with override_minutes.
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO attendance.day_overrides (
                      tenant_id, employee_id, branch_id, day,
                      status, source_type, source_id, override_kind, payload
                    ) VALUES (
                      :tenant_id, :employee_id, :branch_id, :day,
                      'PRESENT_OVERRIDE', 'ATTENDANCE_CORRECTION', :source_id, 'CORRECTION',
                      CAST(:payload AS jsonb)
                    )
                    """
                ),
                {
                    "tenant_id": tenant["tenant_id"],
                    "employee_id": emp_id,
                    "branch_id": tenant["branch_id"],
                    "day": business_day,
                    "source_id": str(uuid.uuid4()),
                    "payload": '{"override_minutes":123}',
                },
            )

        days = client.get(
            f"/api/v1/attendance/me/days?from={business_day}&to={business_day}",
            headers=_auth(emp_token),
        )
        assert days.status_code == 200, days.text
        item = days.json()["data"]["items"][0]
        assert int(item["effective_minutes"]) == 123
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_auto_close_worker_closes_open_session_and_rolls_up(monkeypatch) -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-punch7",
    )
    employee_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-punch7",
    )
    created_users = [admin["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.attendance.router_ess",
                "app.domains.notifications.router",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Punch",
            last_name="User",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=emp_id,
            user_id=employee_user["user_id"],
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])[
            "access_token"
        ]

        from app.domains.attendance import service_punching

        start = datetime(2026, 2, 20, 9, 0, tzinfo=timezone.utc)
        now = {"ts": start}

        def _fake_now() -> datetime:
            return now["ts"]

        monkeypatch.setattr(service_punching, "utcnow", _fake_now)

        # Punch-in only (leave OPEN session).
        r1 = client.post("/api/v1/attendance/me/punch-in", headers=_auth(emp_token), json={})
        assert r1.status_code == 200, r1.text

        # Run worker with a future timestamp that exceeds both midnight and max session hours.
        from app.worker.attendance_session_worker import run_once

        closed = run_once(now_ts=start + timedelta(hours=20))
        assert closed >= 1

        tz = _branch_tz(engine, tenant_id=tenant["tenant_id"], branch_id=tenant["branch_id"])
        business_day = start.astimezone(tz).date()

        with engine.connect() as conn:
            s = conn.execute(
                text(
                    """
                    SELECT id, status, anomaly_code, minutes
                    FROM attendance.work_sessions
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                    ORDER BY created_at ASC, id ASC
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "employee_id": emp_id},
            ).first()
            assert s is not None
            session_id = str(s[0])
            assert str(s[1]) == "AUTO_CLOSED"
            assert str(s[2]) == "MISSING_OUT"
            assert int(s[3]) >= 0

            d = conn.execute(
                text(
                    """
                    SELECT total_minutes, has_open_session
                    FROM attendance.attendance_daily
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                      AND business_date = :day
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "employee_id": emp_id, "day": business_day},
            ).first()
            assert d is not None
            assert bool(d[1]) is False

            a = conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM audit.audit_log
                    WHERE tenant_id = :tenant_id
                      AND entity_id = :entity_id
                      AND action = 'attendance.session.auto_closed'
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "entity_id": session_id},
            ).scalar()
            assert int(a or 0) >= 1

            # Optional notification outbox row (idempotent dedupe).
            o = conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM workflow.notification_outbox
                    WHERE tenant_id = :tenant_id
                      AND template_code = 'attendance.session.auto_closed'
                    """
                ),
                {"tenant_id": tenant["tenant_id"]},
            ).scalar()
            assert int(o or 0) >= 1
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_idempotency_key_returns_same_result(monkeypatch) -> None:
    db_url = os.environ["DATABASE_URL"]
    engine = create_engine(db_url, pool_pre_ping=True)

    tenant = seed_tenant_company(engine)
    admin = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-punch8",
    )
    employee_user = seed_user(
        engine,
        tenant_id=tenant["tenant_id"],
        company_id=tenant["company_id"],
        branch_id=tenant["branch_id"],
        role_code="EMPLOYEE",
        email_prefix="emp-punch8",
    )
    created_users = [admin["user_id"], employee_user["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.hr_core.router_hr",
                "app.domains.attendance.router_ess",
            )
        )

        admin_token = login(client, email=admin["email"], password=admin["password"])[
            "access_token"
        ]

        emp_id = create_employee(
            client,
            token=admin_token,
            company_id=tenant["company_id"],
            branch_id=tenant["branch_id"],
            employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
            first_name="Punch",
            last_name="User",
        )
        link_user_to_employee(
            client,
            token=admin_token,
            employee_id=emp_id,
            user_id=employee_user["user_id"],
        )

        emp_token = login(client, email=employee_user["email"], password=employee_user["password"])[
            "access_token"
        ]

        from app.domains.attendance import service_punching

        now = {"ts": datetime(2026, 2, 20, 9, 0, tzinfo=timezone.utc)}

        def _fake_now() -> datetime:
            return now["ts"]

        monkeypatch.setattr(service_punching, "utcnow", _fake_now)

        r1 = client.post(
            "/api/v1/attendance/me/punch-in",
            headers=_auth(emp_token),
            json={"idempotency_key": "K-IN-1"},
        )
        assert r1.status_code == 200, r1.text

        r2 = client.post(
            "/api/v1/attendance/me/punch-in",
            headers=_auth(emp_token),
            json={"idempotency_key": "K-IN-1"},
        )
        assert r2.status_code == 200, r2.text

        now["ts"] = now["ts"] + timedelta(hours=1)
        r3 = client.post(
            "/api/v1/attendance/me/punch-out",
            headers=_auth(emp_token),
            json={"idempotency_key": "K-OUT-1"},
        )
        assert r3.status_code == 200, r3.text

        r4 = client.post(
            "/api/v1/attendance/me/punch-out",
            headers=_auth(emp_token),
            json={"idempotency_key": "K-OUT-1"},
        )
        assert r4.status_code == 200, r4.text

        with engine.connect() as conn:
            c1 = conn.execute(
                text(
                    """
                    SELECT count(*)
                    FROM attendance.punches
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                      AND idempotency_key IN ('K-IN-1','K-OUT-1')
                    """
                ),
                {"tenant_id": tenant["tenant_id"], "employee_id": emp_id},
            ).scalar()
            assert int(c1 or 0) == 2
    finally:
        cleanup(engine, tenant_id=tenant["tenant_id"], user_ids=created_users)


def test_tenant_isolation_admin_settings_scope_mismatch() -> None:
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
        email_prefix="admin-punch9a",
    )
    admin_b = seed_user(
        engine,
        tenant_id=tenant_b["tenant_id"],
        company_id=tenant_b["company_id"],
        branch_id=tenant_b["branch_id"],
        role_code="ADMIN",
        email_prefix="admin-punch9b",
    )
    created_users = [admin_a["user_id"], admin_b["user_id"]]

    try:
        from fastapi.testclient import TestClient

        client = TestClient(
            make_app(
                "app.auth.router",
                "app.domains.attendance.router_admin",
            )
        )

        token_b = login(client, email=admin_b["email"], password=admin_b["password"])[
            "access_token"
        ]

        # Admin B cannot query settings for tenant A's branch due to scope mismatch hardening.
        r = client.get(
            f"/api/v1/attendance/punch-settings?branch_id={tenant_a['branch_id']}",
            headers=_auth(token_b),
        )
        assert r.status_code == 400, r.text
        assert r.json()["error"]["code"] == "iam.scope.mismatch"
    finally:
        cleanup(engine, tenant_id=tenant_a["tenant_id"], user_ids=[])
        cleanup(engine, tenant_id=tenant_b["tenant_id"], user_ids=created_users)

