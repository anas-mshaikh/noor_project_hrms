"""
Pydantic schemas for HR profile change requests (Milestone 6).

We intentionally keep `change_set` as an untyped dict in the API contract.
Reason:
- The domain enforces a controlled set of fields, but we want to return
  stable AppError codes (400 hr.profile_change.invalid_change_set) instead of
  FastAPI/Pydantic 422 validation errors.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


ProfileChangeStatus = Literal["PENDING", "APPROVED", "REJECTED", "CANCELED"]


class ProfileChangeCreateIn(BaseModel):
    """ESS submission payload for a new profile change request."""

    change_set: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = Field(default=None, max_length=200)


class ProfileChangeRequestOut(BaseModel):
    """API-friendly representation of a profile change request."""

    id: UUID
    tenant_id: UUID
    employee_id: UUID
    created_by_user_id: UUID

    status: ProfileChangeStatus
    workflow_request_id: UUID | None

    change_set: dict[str, Any]
    idempotency_key: str | None

    decided_at: datetime | None
    decided_by_user_id: UUID | None

    created_at: datetime
    updated_at: datetime


class ProfileChangeRequestListOut(BaseModel):
    """Cursor-paginated list response."""

    items: list[ProfileChangeRequestOut]
    next_cursor: str | None


class ProfileChangeSubmitOut(BaseModel):
    """Create endpoint response (same as request out)."""

    request: ProfileChangeRequestOut


class ProfileChangeCancelOut(BaseModel):
    """Cancel endpoint response."""

    id: UUID
    status: ProfileChangeStatus
