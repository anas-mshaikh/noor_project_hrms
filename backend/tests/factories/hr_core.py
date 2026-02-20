"""
HR Core factories (API-level).

These helpers build higher-level domain objects using HR endpoints.

Why:
- Keeps tests focused on domain behavior rather than request payload plumbing.
- Ensures consistent payload shapes across the suite.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from tests.support.api_client import ApiClient


def create_employee(
    api: ApiClient,
    *,
    company_id: str,
    branch_id: str,
    employee_code: str,
    first_name: str,
    last_name: str,
    manager_employee_id: str | None = None,
) -> str:
    """Create an employee using the HR API and return employee_id."""

    payload: dict[str, Any] = {
        "person": {"first_name": first_name, "last_name": last_name, "address": {}},
        "employee": {"company_id": company_id, "employee_code": employee_code, "status": "ACTIVE"},
        "employment": {"start_date": str(date(2026, 1, 1)), "branch_id": branch_id, "is_primary": True},
    }
    if manager_employee_id:
        payload["employment"]["manager_employee_id"] = manager_employee_id

    data = api.post("/api/v1/hr/employees", json=payload)
    return str(data["employee"]["id"])


def link_user_to_employee(api: ApiClient, *, employee_id: str, user_id: str) -> None:
    """Link an IAM user to an employee (ESS linkage)."""

    api.post(f"/api/v1/hr/employees/{employee_id}/link-user", json={"user_id": user_id})

