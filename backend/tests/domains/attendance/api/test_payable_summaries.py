from __future__ import annotations

import uuid
from datetime import date, datetime, timezone

import pytest
import sqlalchemy as sa

from tests.factories import hr_core as hr_core_factory
from tests.support.api_client import ApiClient


pytestmark = [pytest.mark.api, pytest.mark.tenant, pytest.mark.rbac]


def _insert_attendance_daily(
    db_engine,
    *,
    tenant_id: str,
    branch_id: str,
    employee_id: str,
    business_date: date,
    total_minutes: int,
) -> None:
    """
    Insert (or upsert) an attendance_daily rollup row for deterministic tests.

    Notes:
    - attendance.attendance_daily uses a legacy unique key:
        (branch_id, business_date, employee_id)
    - id has no server default in baseline, so we set it explicitly.
    """

    with db_engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO attendance.attendance_daily (
                  id,
                  tenant_id,
                  branch_id,
                  business_date,
                  employee_id,
                  total_minutes,
                  source_breakdown,
                  has_open_session
                ) VALUES (
                  :id,
                  :tenant_id,
                  :branch_id,
                  :business_date,
                  :employee_id,
                  :total_minutes,
                  '{}'::jsonb,
                  false
                )
                ON CONFLICT (branch_id, business_date, employee_id)
                DO UPDATE SET
                  total_minutes = EXCLUDED.total_minutes,
                  source_breakdown = EXCLUDED.source_breakdown,
                  has_open_session = EXCLUDED.has_open_session
                WHERE attendance.attendance_daily.tenant_id = EXCLUDED.tenant_id
                """
            ),
            {
                "id": str(uuid.uuid4()),
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "business_date": business_date,
                "employee_id": employee_id,
                "total_minutes": int(total_minutes),
            },
        )


def _insert_leave_override(
    db_engine,
    *,
    tenant_id: str,
    branch_id: str,
    employee_id: str,
    day: date,
) -> None:
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO attendance.day_overrides (
                  tenant_id, employee_id, branch_id, day,
                  override_kind, status, source_type, source_id
                ) VALUES (
                  :tenant_id, :employee_id, :branch_id, :day,
                  'LEAVE', 'ON_LEAVE', 'LEAVE_REQUEST', :source_id
                )
                """
            ),
            {
                "tenant_id": tenant_id,
                "employee_id": employee_id,
                "branch_id": branch_id,
                "day": day,
                "source_id": str(uuid.uuid4()),
            },
        )


def _insert_correction_override_minutes(
    db_engine,
    *,
    tenant_id: str,
    branch_id: str,
    employee_id: str,
    day: date,
    override_minutes: int,
) -> None:
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO attendance.day_overrides (
                  tenant_id, employee_id, branch_id, day,
                  override_kind, status, source_type, source_id,
                  payload
                ) VALUES (
                  :tenant_id, :employee_id, :branch_id, :day,
                  'CORRECTION', 'PRESENT_OVERRIDE', 'ATTENDANCE_CORRECTION', :source_id,
                  CAST(:payload AS jsonb)
                )
                """
            ),
            {
                "tenant_id": tenant_id,
                "employee_id": employee_id,
                "branch_id": branch_id,
                "day": day,
                "source_id": str(uuid.uuid4()),
                "payload": f'{{"override_minutes": {int(override_minutes)}}}',
            },
        )


def _insert_branch_holiday(
    db_engine,
    *,
    tenant_id: str,
    branch_id: str,
    day: date,
) -> None:
    with db_engine.begin() as conn:
        conn.execute(
            sa.text(
                """
                INSERT INTO leave.holidays (tenant_id, company_id, branch_id, day, name)
                VALUES (:tenant_id, NULL, :branch_id, :day, :name)
                ON CONFLICT DO NOTHING
                """
            ),
            {
                "tenant_id": tenant_id,
                "branch_id": branch_id,
                "day": day,
                "name": f"Holiday {day.isoformat()}",
            },
        )


def _setup_employee_with_default_shift(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> tuple[ApiClient, ApiClient, object, str]:
    """
    Create:
    - tenant
    - ADMIN actor (for HR + roster setup)
    - EMPLOYEE actor (for ESS reads)
    - HR employee + employee_user_link
    - branch default shift (09:00-18:00, break 60 => expected 480)

    Returns (admin_api, employee_api, tenant, employee_id).
    """

    client = client_factory(
        [
            "app.auth.router",
            "app.domains.hr_core.router_hr",
            "app.domains.roster.router",
            "app.domains.attendance.router_ess",
            "app.domains.attendance.router_admin",
        ]
    )
    tenant = tenant_factory()

    admin = actor_factory(client, tenant, "ADMIN")
    employee_user = actor_factory(client, tenant, "EMPLOYEE")

    admin_api = ApiClient(client=client, headers=admin.headers())
    employee_api = ApiClient(client=client, headers=employee_user.headers())

    shift = admin_api.post(
        f"/api/v1/roster/branches/{tenant.branch_id}/shifts",
        json={
            "code": f"DEF_{uuid.uuid4().hex[:6].upper()}",
            "name": "Default Shift",
            "start_time": "09:00",
            "end_time": "18:00",
            "break_minutes": 60,
        },
    )
    admin_api.put(
        f"/api/v1/roster/branches/{tenant.branch_id}/default-shift",
        json={"shift_template_id": shift["id"]},
    )

    emp_id = hr_core_factory.create_employee(
        admin_api,
        company_id=tenant.company_id,
        branch_id=tenant.branch_id,
        employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
        first_name="Payable",
        last_name="User",
    )
    hr_core_factory.link_user_to_employee(
        admin_api,
        employee_id=emp_id,
        user_id=employee_user.user.user_id,  # type: ignore[attr-defined]
    )

    return admin_api, employee_api, tenant, emp_id


def test_payable_summary_workday_present(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # Arrange
    _admin_api, employee_api, tenant, emp_id = _setup_employee_with_default_shift(
        client_factory, tenant_factory, actor_factory, db_engine
    )

    target_day = date(2026, 2, 18)  # Wed
    _insert_attendance_daily(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=emp_id,
        business_date=target_day,
        total_minutes=300,
    )

    # Act
    out = employee_api.get(
        "/api/v1/attendance/me/payable-days",
        params={"from": str(target_day), "to": str(target_day)},
    )

    # Assert
    assert out["items"]
    row = out["items"][0]
    assert row["day"] == str(target_day)
    assert row["day_type"] == "WORKDAY"
    assert int(row["expected_minutes"]) == 480
    assert int(row["worked_minutes"]) == 300
    assert int(row["payable_minutes"]) == 300
    assert row["presence_status"] == "PRESENT"


def test_payable_summary_workday_absent(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # Arrange
    _admin_api, employee_api, _tenant, _emp_id = _setup_employee_with_default_shift(
        client_factory, tenant_factory, actor_factory, db_engine
    )

    target_day = date(2026, 2, 18)

    # Act
    out = employee_api.get(
        "/api/v1/attendance/me/payable-days",
        params={"from": str(target_day), "to": str(target_day)},
    )

    # Assert
    row = out["items"][0]
    assert row["day_type"] == "WORKDAY"
    assert int(row["expected_minutes"]) == 480
    assert int(row["worked_minutes"]) == 0
    assert int(row["payable_minutes"]) == 0
    assert row["presence_status"] == "ABSENT"


def test_payable_summary_on_leave_override(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # Arrange
    _admin_api, employee_api, tenant, emp_id = _setup_employee_with_default_shift(
        client_factory, tenant_factory, actor_factory, db_engine
    )

    target_day = date(2026, 2, 18)
    _insert_leave_override(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=emp_id,
        day=target_day,
    )

    # Act
    out = employee_api.get(
        "/api/v1/attendance/me/payable-days",
        params={"from": str(target_day), "to": str(target_day)},
    )

    # Assert
    row = out["items"][0]
    assert row["day_type"] == "ON_LEAVE"
    assert int(row["expected_minutes"]) == 0
    assert int(row["worked_minutes"]) == 0
    assert int(row["payable_minutes"]) == 0
    assert row["presence_status"] == "N_A"


def test_payable_summary_correction_override_minutes(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # Arrange
    _admin_api, employee_api, tenant, emp_id = _setup_employee_with_default_shift(
        client_factory, tenant_factory, actor_factory, db_engine
    )

    target_day = date(2026, 2, 18)
    _insert_attendance_daily(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=emp_id,
        business_date=target_day,
        total_minutes=120,
    )
    _insert_correction_override_minutes(
        db_engine,
        tenant_id=tenant.tenant_id,
        branch_id=tenant.branch_id,
        employee_id=emp_id,
        day=target_day,
        override_minutes=240,
    )

    # Act
    out = employee_api.get(
        "/api/v1/attendance/me/payable-days",
        params={"from": str(target_day), "to": str(target_day)},
    )

    # Assert
    row = out["items"][0]
    assert row["day_type"] == "WORKDAY"
    assert int(row["expected_minutes"]) == 480
    assert int(row["worked_minutes"]) == 240
    assert int(row["payable_minutes"]) == 240
    assert row["presence_status"] == "PRESENT"


def test_payable_summary_weekoff_and_holiday(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # Arrange
    _admin_api, employee_api, tenant, _emp_id = _setup_employee_with_default_shift(
        client_factory, tenant_factory, actor_factory, db_engine
    )

    holiday_day = date(2026, 2, 19)  # Thu (workday)
    weekoff_day = date(2026, 2, 20)  # Fri (weekly off in baseline defaults)

    _insert_branch_holiday(db_engine, tenant_id=tenant.tenant_id, branch_id=tenant.branch_id, day=holiday_day)

    # Act: holiday
    out1 = employee_api.get(
        "/api/v1/attendance/me/payable-days",
        params={"from": str(holiday_day), "to": str(holiday_day)},
    )
    # Act: weekoff
    out2 = employee_api.get(
        "/api/v1/attendance/me/payable-days",
        params={"from": str(weekoff_day), "to": str(weekoff_day)},
    )

    # Assert: holiday -> N/A + 0
    r1 = out1["items"][0]
    assert r1["day_type"] == "HOLIDAY"
    assert int(r1["expected_minutes"]) == 0
    assert int(r1["payable_minutes"]) == 0
    assert r1["presence_status"] == "N_A"

    # Assert: weekoff -> N/A + 0
    r2 = out2["items"][0]
    assert r2["day_type"] == "WEEKOFF"
    assert int(r2["expected_minutes"]) == 0
    assert int(r2["payable_minutes"]) == 0
    assert r2["presence_status"] == "N_A"


def test_payable_recompute_upserts_idempotent(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
    monkeypatch,
) -> None:
    # Arrange
    _admin_api, employee_api, _tenant, _emp_id = _setup_employee_with_default_shift(
        client_factory, tenant_factory, actor_factory, db_engine
    )

    target_day = date(2026, 2, 18)

    # Patch compute clock so we can assert computed_at changes.
    from app.domains.attendance import service_payable

    t1 = datetime(2026, 2, 18, 9, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 2, 18, 10, 0, tzinfo=timezone.utc)
    now = {"ts": t1}

    def _fake_now() -> datetime:
        return now["ts"]

    monkeypatch.setattr(service_payable, "_utcnow", _fake_now)

    # Act: first compute
    out1 = employee_api.get(
        "/api/v1/attendance/me/payable-days",
        params={"from": str(target_day), "to": str(target_day)},
    )
    computed1 = out1["items"][0]["computed_at"]

    # Act: second compute (new timestamp)
    now["ts"] = t2
    out2 = employee_api.get(
        "/api/v1/attendance/me/payable-days",
        params={"from": str(target_day), "to": str(target_day)},
    )
    computed2 = out2["items"][0]["computed_at"]

    # Assert: computed_at updates (upsert semantics)
    assert computed1 != computed2


def test_tenant_isolation_roster_and_payable(
    client_factory,
    tenant_factory,
    actor_factory,
    db_engine,
) -> None:
    # Arrange: build one app shared across both tenants
    client = client_factory(
        [
            "app.auth.router",
            "app.domains.hr_core.router_hr",
            "app.domains.roster.router",
            "app.domains.attendance.router_ess",
            "app.domains.attendance.router_admin",
        ]
    )

    tenant_a = tenant_factory()
    tenant_b = tenant_factory()

    admin_a = actor_factory(client, tenant_a, "ADMIN")
    admin_b = actor_factory(client, tenant_b, "ADMIN")

    api_a = ApiClient(client=client, headers=admin_a.headers())
    api_b = ApiClient(client=client, headers=admin_b.headers())

    # Create a shift in tenant A.
    shift_a = api_a.post(
        f"/api/v1/roster/branches/{tenant_a.branch_id}/shifts",
        json={
            "code": f"ISO_{uuid.uuid4().hex[:6].upper()}",
            "name": "Isolation Shift",
            "start_time": "09:00",
            "end_time": "10:00",
            "break_minutes": 0,
        },
    )

    # Act/Assert: tenant B cannot patch tenant A's shift by id (404, no leak).
    r = client.patch(
        f"/api/v1/roster/shifts/{shift_a['id']}",
        headers=admin_b.headers(),
        json={"name": "Hacked"},
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "roster.shift.not_found"

