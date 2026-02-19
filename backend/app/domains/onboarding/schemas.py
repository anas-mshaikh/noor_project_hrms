"""
Pydantic schemas for onboarding v2 (Milestone 6).

We keep payload fields flexible (dict[str, Any]) for v1 because the onboarding
form/task catalog is expected to evolve. The services enforce key invariants and
return stable AppError codes for invalid operations.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


OnboardingTaskType = Literal["DOCUMENT", "FORM", "ACK"]
OnboardingAssigneeType = Literal["EMPLOYEE", "MANAGER", "ROLE"]

OnboardingBundleStatus = Literal["ACTIVE", "COMPLETED", "CANCELED"]
OnboardingTaskStatus = Literal[
    "PENDING", "SUBMITTED", "APPROVED", "REJECTED", "SKIPPED"
]


class PlanTemplateCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    is_active: bool = True

    # Optional scoping fields (v1: stored, not enforced automatically).
    company_id: UUID | None = None
    branch_id: UUID | None = None
    job_title_id: UUID | None = None
    grade_id: UUID | None = None
    org_unit_id: UUID | None = None


class PlanTemplateOut(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    is_active: bool

    company_id: UUID | None
    branch_id: UUID | None
    job_title_id: UUID | None
    grade_id: UUID | None
    org_unit_id: UUID | None

    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class PlanTemplateTaskCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=200)
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=5000)
    task_type: OnboardingTaskType
    required: bool = True
    order_index: int = Field(ge=0)
    due_days: int | None = Field(default=None, ge=0)

    assignee_type: OnboardingAssigneeType
    assignee_role_code: str | None = Field(default=None, max_length=64)

    required_document_type_code: str | None = Field(default=None, max_length=64)
    requires_document_verification: bool = False

    form_schema: dict[str, Any] | None = None
    form_profile_change_mapping: dict[str, Any] | None = None


class PlanTemplateTaskOut(BaseModel):
    id: UUID
    tenant_id: UUID
    plan_template_id: UUID
    code: str
    title: str
    description: str | None
    task_type: OnboardingTaskType
    required: bool
    order_index: int
    due_days: int | None
    assignee_type: OnboardingAssigneeType
    assignee_role_code: str | None
    required_document_type_code: str | None
    requires_document_verification: bool
    form_schema: dict[str, Any] | None
    form_profile_change_mapping: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class BundleCreateIn(BaseModel):
    template_code: str = Field(min_length=1, max_length=200)
    branch_id: UUID


class EmployeeBundleOut(BaseModel):
    id: UUID
    tenant_id: UUID
    employee_id: UUID
    plan_template_id: UUID
    branch_id: UUID
    status: OnboardingBundleStatus
    created_by_user_id: UUID
    created_at: datetime
    updated_at: datetime


class EmployeeTaskOut(BaseModel):
    id: UUID
    tenant_id: UUID
    bundle_id: UUID

    task_code: str
    title: str
    description: str | None
    task_type: OnboardingTaskType
    required: bool
    order_index: int
    due_on: date | None

    assignee_type: OnboardingAssigneeType
    assignee_role_code: str | None
    assigned_to_user_id: UUID | None

    status: OnboardingTaskStatus
    submission_payload: dict[str, Any] | None

    related_document_id: UUID | None
    verification_workflow_request_id: UUID | None

    decided_at: datetime | None
    decided_by_user_id: UUID | None

    created_at: datetime
    updated_at: datetime


class BundleDetailOut(BaseModel):
    bundle: EmployeeBundleOut
    tasks: list[EmployeeTaskOut]


class EssOnboardingOut(BaseModel):
    bundle: EmployeeBundleOut | None
    tasks: list[EmployeeTaskOut]


class SubmitFormIn(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)


class SubmitPacketOut(BaseModel):
    profile_change_request_id: UUID
    workflow_request_id: UUID
