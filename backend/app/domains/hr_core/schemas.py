from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


EmployeeStatus = Literal["ACTIVE", "INACTIVE", "TERMINATED"]


class PersonCreateIn(BaseModel):
    first_name: str = Field(min_length=1, max_length=200)
    last_name: str = Field(min_length=1, max_length=200)
    dob: date | None = None
    nationality: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    address: dict[str, Any] = Field(default_factory=dict)


class EmployeeCreateFields(BaseModel):
    company_id: UUID
    employee_code: str = Field(min_length=1, max_length=64)
    join_date: date | None = None
    status: EmployeeStatus = "ACTIVE"


class EmploymentCreateIn(BaseModel):
    start_date: date
    branch_id: UUID
    org_unit_id: UUID | None = None
    job_title_id: UUID | None = None
    grade_id: UUID | None = None
    manager_employee_id: UUID | None = None
    is_primary: bool = True


class EmployeeCreateIn(BaseModel):
    person: PersonCreateIn
    employee: EmployeeCreateFields
    employment: EmploymentCreateIn


class PersonPatchIn(BaseModel):
    first_name: str | None = Field(default=None, min_length=1, max_length=200)
    last_name: str | None = Field(default=None, min_length=1, max_length=200)
    dob: date | None = None
    nationality: str | None = Field(default=None, max_length=100)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    address: dict[str, Any] | None = None


class EmployeePatchFields(BaseModel):
    status: EmployeeStatus | None = None
    join_date: date | None = None
    termination_date: date | None = None


class EmployeePatchIn(BaseModel):
    person: PersonPatchIn | None = None
    employee: EmployeePatchFields | None = None


class EmploymentChangeIn(BaseModel):
    start_date: date
    branch_id: UUID
    org_unit_id: UUID | None = None
    job_title_id: UUID | None = None
    grade_id: UUID | None = None
    manager_employee_id: UUID | None = None


class EmployeeLinkUserIn(BaseModel):
    user_id: UUID


class PersonOut(BaseModel):
    id: UUID
    tenant_id: UUID
    first_name: str
    last_name: str
    dob: date | None
    nationality: str | None
    email: EmailStr | None
    phone: str | None
    address: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class EmployeeOut(BaseModel):
    id: UUID
    tenant_id: UUID
    company_id: UUID
    person_id: UUID
    employee_code: str
    status: EmployeeStatus
    join_date: date | None
    termination_date: date | None
    created_at: datetime
    updated_at: datetime


class EmploymentOut(BaseModel):
    id: UUID
    tenant_id: UUID
    company_id: UUID
    employee_id: UUID
    branch_id: UUID
    org_unit_id: UUID | None
    job_title_id: UUID | None
    grade_id: UUID | None
    manager_employee_id: UUID | None
    start_date: date
    end_date: date | None
    is_primary: bool | None
    created_at: datetime
    updated_at: datetime


class ManagerSummaryOut(BaseModel):
    employee_id: UUID
    display_name: str
    employee_code: str | None = None


class Employee360Out(BaseModel):
    employee: EmployeeOut
    person: PersonOut
    current_employment: EmploymentOut | None
    manager: ManagerSummaryOut | None


class EmployeeDirectoryRowOut(BaseModel):
    employee_id: UUID
    employee_code: str
    status: EmployeeStatus
    full_name: str
    email: EmailStr | None
    phone: str | None
    branch_id: UUID | None
    org_unit_id: UUID | None
    manager_employee_id: UUID | None
    manager_name: str | None


class EmployeeUserLinkOut(BaseModel):
    employee_id: UUID
    user_id: UUID
    created_at: datetime


class EssProfilePatchIn(BaseModel):
    """
    ESS profile patch: allow safe fields only.

    We deliberately allow extra keys so we can return a stable 400 AppError
    instead of a generic 422 validation error.
    """

    model_config = ConfigDict(extra="allow")

    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=32)
    address: dict[str, Any] | None = None


class PagingOut(BaseModel):
    limit: int
    offset: int
    total: int


class MSSEmployeeSummaryOut(BaseModel):
    employee_id: UUID
    employee_code: str
    display_name: str
    status: EmployeeStatus
    branch_id: UUID | None
    org_unit_id: UUID | None
    job_title_id: UUID | None
    grade_id: UUID | None
    manager_employee_id: UUID | None
    relationship_depth: int


class MSSTeamListOut(BaseModel):
    items: list[MSSEmployeeSummaryOut]
    paging: PagingOut


class MSSPersonOut(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr | None
    phone: str | None


class MSSEmployeeOut(BaseModel):
    id: UUID
    employee_code: str
    status: EmployeeStatus
    join_date: date | None
    termination_date: date | None


class MSSEmploymentOut(BaseModel):
    branch_id: UUID
    org_unit_id: UUID | None
    job_title_id: UUID | None
    grade_id: UUID | None
    manager_employee_id: UUID | None


class MSSEmployeeProfileOut(BaseModel):
    employee: MSSEmployeeOut
    person: MSSPersonOut
    current_employment: MSSEmploymentOut | None
    manager: ManagerSummaryOut | None
