from __future__ import annotations

import uuid
from datetime import date

import pytest

from tests.factories import hr_core as hr_core_factory
from tests.support.api_client import ApiClient


pytestmark = [pytest.mark.api, pytest.mark.tenant, pytest.mark.rbac]


def test_default_shift_and_assignment_resolution(
    client_factory,
    tenant_factory,
    actor_factory,
) -> None:
    # Arrange
    client = client_factory(
        [
            "app.auth.router",
            "app.domains.hr_core.router_hr",
            "app.domains.roster.router",
            "app.domains.attendance.router_admin",
        ]
    )
    tenant = tenant_factory()
    admin = actor_factory(client, tenant, "ADMIN")
    api = ApiClient(client=client, headers=admin.headers())

    shift_a = api.post(
        f"/api/v1/roster/branches/{tenant.branch_id}/shifts",
        json={
            "code": f"A_{uuid.uuid4().hex[:6].upper()}",
            "name": "Default Shift",
            "start_time": "09:00",
            "end_time": "18:00",
            "break_minutes": 60,
        },
    )
    shift_b = api.post(
        f"/api/v1/roster/branches/{tenant.branch_id}/shifts",
        json={
            "code": f"B_{uuid.uuid4().hex[:6].upper()}",
            "name": "Assigned Shift",
            "start_time": "08:00",
            "end_time": "12:00",
            "break_minutes": 0,
        },
    )

    api.put(
        f"/api/v1/roster/branches/{tenant.branch_id}/default-shift",
        json={"shift_template_id": shift_a["id"]},
    )

    emp_id = hr_core_factory.create_employee(
        api,
        company_id=tenant.company_id,
        branch_id=tenant.branch_id,
        employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
        first_name="Roster",
        last_name="Employee",
    )

    target_day = date(2026, 2, 18)  # Wednesday (workday under default weekly off)

    # Act: compute payable summary with only default shift
    api.post(
        "/api/v1/attendance/payable/recompute",
        json={"from": str(target_day), "to": str(target_day), "employee_ids": [emp_id]},
    )
    listed = api.get(
        "/api/v1/attendance/admin/payable-days",
        params={"from": str(target_day), "to": str(target_day), "employee_id": emp_id, "limit": 10},
    )

    # Assert: default shift used (expected minutes from shift A)
    assert listed["items"], "expected one summary row"
    row = listed["items"][0]
    assert row["shift_template_id"] == shift_a["id"]
    assert int(row["expected_minutes"]) == int(shift_a["expected_minutes"])

    # Act: assign shift B and recompute
    api.post(
        f"/api/v1/roster/employees/{emp_id}/assignments",
        json={
            "shift_template_id": shift_b["id"],
            "effective_from": "2026-02-01",
        },
    )
    api.post(
        "/api/v1/attendance/payable/recompute",
        json={"from": str(target_day), "to": str(target_day), "employee_ids": [emp_id]},
    )
    listed2 = api.get(
        "/api/v1/attendance/admin/payable-days",
        params={"from": str(target_day), "to": str(target_day), "employee_id": emp_id, "limit": 10},
    )

    # Assert: assignment wins over default
    row2 = listed2["items"][0]
    assert row2["shift_template_id"] == shift_b["id"]
    assert int(row2["expected_minutes"]) == int(shift_b["expected_minutes"])


def test_roster_override_wins_over_assignment(
    client_factory,
    tenant_factory,
    actor_factory,
) -> None:
    # Arrange
    client = client_factory(
        [
            "app.auth.router",
            "app.domains.hr_core.router_hr",
            "app.domains.roster.router",
            "app.domains.attendance.router_admin",
        ]
    )
    tenant = tenant_factory()
    admin = actor_factory(client, tenant, "ADMIN")
    api = ApiClient(client=client, headers=admin.headers())

    shift_b = api.post(
        f"/api/v1/roster/branches/{tenant.branch_id}/shifts",
        json={
            "code": f"B_{uuid.uuid4().hex[:6].upper()}",
            "name": "Assigned Shift",
            "start_time": "08:00",
            "end_time": "12:00",
            "break_minutes": 0,
        },
    )
    shift_c = api.post(
        f"/api/v1/roster/branches/{tenant.branch_id}/shifts",
        json={
            "code": f"C_{uuid.uuid4().hex[:6].upper()}",
            "name": "Override Shift",
            "start_time": "10:00",
            "end_time": "15:00",
            "break_minutes": 0,
        },
    )

    emp_id = hr_core_factory.create_employee(
        api,
        company_id=tenant.company_id,
        branch_id=tenant.branch_id,
        employee_code=f"E{uuid.uuid4().hex[:6].upper()}",
        first_name="Override",
        last_name="Employee",
    )

    api.post(
        f"/api/v1/roster/employees/{emp_id}/assignments",
        json={
            "shift_template_id": shift_b["id"],
            "effective_from": "2026-02-01",
        },
    )

    target_day = date(2026, 2, 18)

    # Act: SHIFT_CHANGE override to shift C for that day
    api.put(
        f"/api/v1/roster/employees/{emp_id}/overrides/{target_day.isoformat()}",
        json={"override_type": "SHIFT_CHANGE", "shift_template_id": shift_c["id"]},
    )
    api.post(
        "/api/v1/attendance/payable/recompute",
        json={"from": str(target_day), "to": str(target_day), "employee_ids": [emp_id]},
    )
    listed = api.get(
        "/api/v1/attendance/admin/payable-days",
        params={"from": str(target_day), "to": str(target_day), "employee_id": emp_id, "limit": 10},
    )

    # Assert: override wins over assignment
    row = listed["items"][0]
    assert row["shift_template_id"] == shift_c["id"]
    assert int(row["expected_minutes"]) == int(shift_c["expected_minutes"])

    # Act: WEEKOFF override forces expected=0 and day_type=WEEKOFF
    api.put(
        f"/api/v1/roster/employees/{emp_id}/overrides/{target_day.isoformat()}",
        json={"override_type": "WEEKOFF"},
    )
    api.post(
        "/api/v1/attendance/payable/recompute",
        json={"from": str(target_day), "to": str(target_day), "employee_ids": [emp_id]},
    )
    listed2 = api.get(
        "/api/v1/attendance/admin/payable-days",
        params={"from": str(target_day), "to": str(target_day), "employee_id": emp_id, "limit": 10},
    )
    row2 = listed2["items"][0]
    assert row2["day_type"] == "WEEKOFF"
    assert int(row2["expected_minutes"]) == 0
    assert int(row2["payable_minutes"]) == 0

