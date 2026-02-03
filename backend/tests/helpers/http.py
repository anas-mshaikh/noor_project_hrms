from __future__ import annotations

from datetime import date
from typing import Any


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def login(client, *, email: str, password: str) -> dict[str, Any]:
    r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["data"]


def create_employee(
    client,
    *,
    token: str,
    company_id: str,
    branch_id: str,
    employee_code: str,
    first_name: str,
    last_name: str,
    email: str | None = None,
    start_date_value: date = date(2026, 1, 1),
    join_date_value: date | None = None,
    status: str = "ACTIVE",
    manager_employee_id: str | None = None,
    org_unit_id: str | None = None,
) -> str:
    payload: dict[str, object] = {
        "person": {"first_name": first_name, "last_name": last_name, "address": {}},
        "employee": {"company_id": company_id, "employee_code": employee_code, "status": status},
        "employment": {"start_date": str(start_date_value), "branch_id": branch_id, "is_primary": True},
    }
    if email is not None:
        payload["person"]["email"] = email  # type: ignore[index]
    if join_date_value is not None:
        payload["employee"]["join_date"] = str(join_date_value)  # type: ignore[index]
    if manager_employee_id is not None:
        payload["employment"]["manager_employee_id"] = manager_employee_id  # type: ignore[index]
    if org_unit_id is not None:
        payload["employment"]["org_unit_id"] = org_unit_id  # type: ignore[index]

    r = client.post("/api/v1/hr/employees", headers=auth_headers(token), json=payload)
    assert r.status_code == 200, r.text
    return r.json()["data"]["employee"]["id"]


def link_user_to_employee(client, *, token: str, employee_id: str, user_id: str) -> None:
    r = client.post(
        f"/api/v1/hr/employees/{employee_id}/link-user",
        headers=auth_headers(token),
        json={"user_id": user_id},
    )
    assert r.status_code == 200, r.text

