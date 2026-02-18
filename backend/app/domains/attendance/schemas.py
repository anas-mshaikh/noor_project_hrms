from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


# ------------------------------------------------------------------
# Effective day status (ESS day view)
# ------------------------------------------------------------------
BaseDayStatus = Literal["PRESENT", "ABSENT"]
OverrideKind = Literal["LEAVE", "CORRECTION"]
OverrideStatus = Literal[
    "ON_LEAVE",
    "PRESENT_OVERRIDE",
    "ABSENT_OVERRIDE",
    "WFH",
    "ON_DUTY",
]
EffectiveStatus = Literal[
    "ON_LEAVE",
    "PRESENT_OVERRIDE",
    "ABSENT_OVERRIDE",
    "WFH",
    "ON_DUTY",
    "PRESENT",
    "ABSENT",
]


class DayOverrideOut(BaseModel):
    kind: OverrideKind
    status: OverrideStatus
    source_type: str
    source_id: UUID


class AttendanceDayOut(BaseModel):
    day: date
    base_status: BaseDayStatus
    effective_status: EffectiveStatus
    override: DayOverrideOut | None


class AttendanceDaysOut(BaseModel):
    items: list[AttendanceDayOut]


# ------------------------------------------------------------------
# Attendance corrections (ESS + admin list)
# ------------------------------------------------------------------
CorrectionType = Literal["MISSED_PUNCH", "MARK_PRESENT", "MARK_ABSENT", "WFH", "ON_DUTY"]
RequestedOverrideStatus = Literal["PRESENT_OVERRIDE", "ABSENT_OVERRIDE", "WFH", "ON_DUTY"]
CorrectionStatus = Literal["PENDING", "APPROVED", "REJECTED", "CANCELED"]


class AttendanceCorrectionCreateIn(BaseModel):
    day: date
    correction_type: CorrectionType
    requested_override_status: RequestedOverrideStatus
    reason: str | None = Field(default=None, max_length=2000)
    evidence_file_ids: list[UUID] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, max_length=200)


class AttendanceCorrectionOut(BaseModel):
    id: UUID
    tenant_id: UUID
    employee_id: UUID
    branch_id: UUID
    day: date
    correction_type: CorrectionType
    requested_override_status: RequestedOverrideStatus
    reason: str | None
    evidence_file_ids: list[UUID]
    status: CorrectionStatus
    workflow_request_id: UUID | None
    idempotency_key: str | None
    created_at: datetime
    updated_at: datetime

    meta: dict[str, Any] | None = None


class AttendanceCorrectionListOut(BaseModel):
    items: list[AttendanceCorrectionOut]
    next_cursor: str | None

