"""
employees/service.py

Domain-level employee operations shared across features.

Important:
- This module is intentionally "thin" and DB-transaction friendly.
- The caller controls commit/rollback so multi-step flows can stay atomic
  (e.g., ATS onboarding conversion creates an employee + onboarding plan in one commit).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.employees.schemas import EmployeeCreateRequest
from app.models.models import Employee


def create_employee_in_db(db: Session, *, store_id: UUID, body: EmployeeCreateRequest) -> Employee:
    """
    Create an Employee ORM object and add it to the current SQLAlchemy session.

    Transaction behavior:
    - This function does NOT commit.
    - It flushes so the caller can read `emp.id` immediately.
    - Integrity errors (e.g., duplicate employee_code per store) will surface on flush/commit.
    """

    emp = Employee(
        store_id=store_id,
        name=body.name,
        employee_code=body.employee_code,
        department=body.department,
    )
    db.add(emp)
    db.flush()  # allocate PK so downstream logic can reference it
    return emp

