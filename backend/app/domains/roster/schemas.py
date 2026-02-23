"""
Roster Pydantic schemas (Milestone 8).

These schemas are intentionally explicit and small:
- v1 needs only shift templates, defaults, assignments, and per-day overrides.
- Future milestones can add richer policy engines (grace/late/overtime) without
  breaking the core contract.
"""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


RosterOverrideType = Literal["SHIFT_CHANGE", "WEEKOFF", "WORKDAY"]


class ShiftTemplateCreateIn(BaseModel):
    """Create a shift template (branch-scoped)."""

    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    start_time: time
    end_time: time
    break_minutes: int = Field(default=0, ge=0, le=24 * 60)

    # Placeholders for future time policy rules.
    grace_minutes: int = Field(default=0, ge=0, le=24 * 60)
    min_full_day_minutes: int | None = Field(default=None, ge=0, le=24 * 60)

    is_active: bool = True


class ShiftTemplatePatchIn(BaseModel):
    """Patch a shift template (partial update)."""

    code: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    start_time: time | None = None
    end_time: time | None = None
    break_minutes: int | None = Field(default=None, ge=0, le=24 * 60)

    grace_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    min_full_day_minutes: int | None = Field(default=None, ge=0, le=24 * 60)

    is_active: bool | None = None


class ShiftTemplateOut(BaseModel):
    """Shift template output (includes derived expected_minutes for convenience)."""

    id: UUID
    tenant_id: UUID
    branch_id: UUID
    code: str
    name: str
    start_time: time
    end_time: time
    break_minutes: int
    grace_minutes: int
    min_full_day_minutes: int | None
    is_active: bool

    expected_minutes: int

    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class BranchDefaultShiftUpsertIn(BaseModel):
    """Set/update a branch default shift."""

    shift_template_id: UUID


class BranchDefaultShiftOut(BaseModel):
    tenant_id: UUID
    branch_id: UUID
    default_shift_template_id: UUID
    created_at: datetime
    updated_at: datetime


class ShiftAssignmentCreateIn(BaseModel):
    """Assign a shift template to an employee (effective dated)."""

    shift_template_id: UUID
    effective_from: date
    effective_to: date | None = None


class ShiftAssignmentOut(BaseModel):
    id: UUID
    tenant_id: UUID
    employee_id: UUID
    branch_id: UUID
    shift_template_id: UUID
    effective_from: date
    effective_to: date | None

    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class RosterOverrideUpsertIn(BaseModel):
    """Upsert a per-employee per-day roster override."""

    override_type: RosterOverrideType
    shift_template_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=2000)


class RosterOverrideOut(BaseModel):
    id: UUID
    tenant_id: UUID
    employee_id: UUID
    branch_id: UUID
    day: date
    override_type: RosterOverrideType
    shift_template_id: UUID | None
    notes: str | None

    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime

