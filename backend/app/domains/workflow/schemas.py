from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


AssigneeType = Literal["MANAGER", "ROLE", "USER"]
ScopeMode = Literal["TENANT", "COMPANY", "BRANCH"]


class WorkflowRequestCreateIn(BaseModel):
    request_type_code: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = Field(default_factory=dict)

    subject_employee_id: UUID | None = None
    entity_type: str | None = Field(default=None, max_length=200)
    entity_id: UUID | None = None

    # Optional hints; the effective scope comes from AuthContext.scope.
    company_id: UUID | None = None
    branch_id: UUID | None = None

    idempotency_key: str | None = Field(default=None, max_length=200)
    comment: str | None = Field(default=None, max_length=2000)


class WorkflowRequestApproveIn(BaseModel):
    comment: str | None = Field(default=None, max_length=2000)


class WorkflowRequestRejectIn(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)


class WorkflowCommentCreateIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class WorkflowAttachmentCreateIn(BaseModel):
    file_id: UUID
    note: str | None = Field(default=None, max_length=2000)


class WorkflowRequestSummaryOut(BaseModel):
    id: UUID
    request_type_code: str
    status: str
    current_step: int

    subject: str | None
    payload: dict[str, Any] | None = None

    tenant_id: UUID
    company_id: UUID
    branch_id: UUID | None

    created_by_user_id: UUID | None
    requester_employee_id: UUID
    subject_employee_id: UUID | None

    entity_type: str | None
    entity_id: UUID | None

    created_at: datetime
    updated_at: datetime


class WorkflowRequestListOut(BaseModel):
    items: list[WorkflowRequestSummaryOut]
    next_cursor: str | None


class WorkflowRequestStepOut(BaseModel):
    id: UUID
    step_order: int

    assignee_type: str | None
    assignee_role_code: str | None
    assignee_user_id: UUID | None
    assignee_user_ids: list[UUID] = Field(default_factory=list)

    decision: str | None
    decided_at: datetime | None
    decided_by_user_id: UUID | None
    comment: str | None
    created_at: datetime


class WorkflowRequestCommentOut(BaseModel):
    id: UUID
    author_user_id: UUID
    body: str
    created_at: datetime


class WorkflowRequestAttachmentOut(BaseModel):
    id: UUID
    file_id: UUID
    uploaded_by_user_id: UUID | None
    note: str | None
    created_at: datetime


class WorkflowRequestEventOut(BaseModel):
    id: UUID
    actor_user_id: UUID | None
    event_type: str
    data: dict[str, Any]
    correlation_id: str | None
    created_at: datetime


class WorkflowRequestDetailOut(BaseModel):
    request: WorkflowRequestSummaryOut
    steps: list[WorkflowRequestStepOut]
    comments: list[WorkflowRequestCommentOut]
    attachments: list[WorkflowRequestAttachmentOut]
    events: list[WorkflowRequestEventOut]


class WorkflowDefinitionCreateIn(BaseModel):
    request_type_code: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=200)
    name: str = Field(min_length=1, max_length=200)
    version: int = Field(ge=1)
    company_id: UUID | None = None


class WorkflowDefinitionStepIn(BaseModel):
    step_index: int = Field(ge=0)
    assignee_type: AssigneeType
    assignee_role_code: str | None = Field(default=None, max_length=64)
    assignee_user_id: UUID | None = None
    scope_mode: ScopeMode = "TENANT"
    fallback_role_code: str | None = Field(default=None, max_length=64)


class WorkflowDefinitionStepsIn(BaseModel):
    steps: list[WorkflowDefinitionStepIn] = Field(min_length=1)


class WorkflowDefinitionStepOut(BaseModel):
    step_index: int
    assignee_type: str
    assignee_role_code: str | None
    assignee_user_id: UUID | None
    scope_mode: str
    fallback_role_code: str | None


class WorkflowDefinitionOut(BaseModel):
    id: UUID
    tenant_id: UUID
    company_id: UUID | None
    request_type_code: str
    code: str | None
    name: str
    version: int | None
    is_active: bool
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime
    steps: list[WorkflowDefinitionStepOut] = Field(default_factory=list)

