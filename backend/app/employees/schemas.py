"""
employees/schemas.py

Pydantic schemas related to employees.

We keep these in a small module so other features (e.g., HR onboarding) can reuse the
same request shapes without importing the entire employees router (which also imports
face recognition dependencies).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class EmployeeCreateRequest(BaseModel):
    """
    Minimal employee creation payload (store-scoped).

    Note: `store_id` is provided by the URL path in our API design, not in the body.
    """

    name: str
    employee_code: str
    department: str


class EmployeeOut(BaseModel):
    id: UUID
    store_id: UUID
    name: str
    employee_code: str
    department: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

