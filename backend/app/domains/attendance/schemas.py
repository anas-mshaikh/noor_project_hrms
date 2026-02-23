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
    # Worked minutes derived from attendance_daily.total_minutes (0 if missing/NULL).
    base_minutes: int
    # Minutes after applying overrides (leave/correction precedence).
    effective_minutes: int
    # Optional first/last timestamps derived from the daily rollup.
    first_in: datetime | None = None
    last_out: datetime | None = None
    # Convenience for UI: indicates an OPEN session exists for the employee.
    has_open_session: bool = False
    # Minute sources derived from attendance_daily.source_breakdown keys.
    sources: list[str] = Field(default_factory=list)
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


# ------------------------------------------------------------------
# Punching v1 (Zoho-style toggle)
# ------------------------------------------------------------------


class PunchSubmitIn(BaseModel):
    """
    Punch-in/out submission payload.

    Notes:
    - `idempotency_key` enables client retries without duplicating punches.
    - `meta` is a future-proof JSON container for non-sensitive client context
      (e.g., device metadata). We intentionally do not enforce a schema in v1.
    """

    idempotency_key: str | None = Field(default=None, max_length=200)
    meta: dict[str, Any] | None = None


class PunchStateOut(BaseModel):
    """Current punch state for the actor's *current* employment branch/day."""

    today_business_date: date
    is_punched_in: bool
    open_session_started_at: datetime | None = None
    base_minutes_today: int
    effective_minutes_today: int
    effective_status_today: EffectiveStatus


class PunchSettingsOut(BaseModel):
    """Branch-level punch configuration (admin view)."""

    tenant_id: UUID
    branch_id: UUID
    is_enabled: bool
    allow_multiple_sessions_per_day: bool
    max_session_hours: int
    require_location: bool
    geo_fence_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class PunchSettingsUpdateIn(BaseModel):
    """Update request for punch settings (partial update via PUT in v1)."""

    is_enabled: bool | None = None
    allow_multiple_sessions_per_day: bool | None = None
    max_session_hours: int | None = Field(default=None, ge=1, le=24)
    require_location: bool | None = None
    geo_fence_json: dict[str, Any] | None = None


# ------------------------------------------------------------------
# Payable day summaries (payroll-ready)
# ------------------------------------------------------------------
PayableDayType = Literal["WORKDAY", "WEEKOFF", "HOLIDAY", "ON_LEAVE", "UNSCHEDULED"]
PayablePresenceStatus = Literal["PRESENT", "ABSENT", "N_A"]


class PayableDaySummaryOut(BaseModel):
    """
    Materialized payable day summary (v1).

    This row is the output of roster schedule resolution + effective worked
    minutes (attendance overrides).
    """

    day: date
    employee_id: UUID
    branch_id: UUID
    shift_template_id: UUID | None = None
    day_type: PayableDayType
    presence_status: PayablePresenceStatus

    expected_minutes: int
    worked_minutes: int
    payable_minutes: int

    anomalies_json: dict[str, Any] | None = None
    source_breakdown: dict[str, Any] | None = None
    computed_at: datetime


class PayableDaysOut(BaseModel):
    items: list[PayableDaySummaryOut]


class PayableDaySummaryListOut(BaseModel):
    items: list[PayableDaySummaryOut]
    next_cursor: str | None


class PayableRecomputeIn(BaseModel):
    """Recompute request payload (admin endpoint)."""

    from_day: date = Field(alias="from")
    to_day: date = Field(alias="to")
    branch_id: UUID | None = None
    employee_ids: list[UUID] = Field(default_factory=list)


class PayableRecomputeOut(BaseModel):
    computed_rows: int
