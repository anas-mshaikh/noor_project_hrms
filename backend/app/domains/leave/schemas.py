from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


LeaveUnit = Literal["DAY", "HALF_DAY"]
HalfDayPart = Literal["AM", "PM"]
LeaveRequestStatus = Literal["DRAFT", "PENDING", "APPROVED", "REJECTED", "CANCELED"]


class LeaveBalanceOut(BaseModel):
    leave_type_code: str
    leave_type_name: str
    period_year: int
    balance_days: float
    used_days: float
    pending_days: float


class LeaveBalancesOut(BaseModel):
    items: list[LeaveBalanceOut]


class LeaveRequestCreateIn(BaseModel):
    leave_type_code: str = Field(min_length=1, max_length=64)
    start_date: date
    end_date: date
    unit: LeaveUnit = "DAY"
    half_day_part: HalfDayPart | None = None
    reason: str | None = Field(default=None, max_length=2000)
    attachment_file_ids: list[UUID] = Field(default_factory=list)
    idempotency_key: str | None = Field(default=None, max_length=200)


class LeaveRequestOut(BaseModel):
    id: UUID
    tenant_id: UUID
    employee_id: UUID
    company_id: UUID | None
    branch_id: UUID | None

    leave_type_code: str
    leave_type_name: str | None = None

    policy_id: UUID
    start_date: date
    end_date: date
    unit: LeaveUnit
    half_day_part: HalfDayPart | None
    requested_days: float
    reason: str | None
    status: LeaveRequestStatus
    workflow_request_id: UUID | None

    created_at: datetime
    updated_at: datetime


class LeaveRequestListOut(BaseModel):
    items: list[LeaveRequestOut]
    next_cursor: str | None


class LeaveRequestCancelOut(BaseModel):
    id: UUID
    status: LeaveRequestStatus


class LeaveTypeCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    is_paid: bool = True
    unit: LeaveUnit = "DAY"
    requires_attachment: bool = False
    allow_negative_balance: bool = False
    max_consecutive_days: int | None = Field(default=None, ge=1)
    min_notice_days: int | None = Field(default=None, ge=0)
    is_active: bool = True


class LeaveTypeOut(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    is_paid: bool
    unit: LeaveUnit
    requires_attachment: bool
    allow_negative_balance: bool
    max_consecutive_days: int | None
    min_notice_days: int | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LeavePolicyCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    company_id: UUID | None = None
    branch_id: UUID | None = None
    effective_from: date
    effective_to: date | None = None
    year_start_month: int = Field(default=1, ge=1, le=12)
    is_active: bool = True


class LeavePolicyOut(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    company_id: UUID | None
    branch_id: UUID | None
    effective_from: date
    effective_to: date | None
    year_start_month: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class LeavePolicyRuleUpsertIn(BaseModel):
    leave_type_code: str = Field(min_length=1, max_length=64)
    annual_entitlement_days: float = Field(default=0, ge=0)
    allow_half_day: bool = False
    requires_attachment: bool | None = None


class LeavePolicyRulesIn(BaseModel):
    rules: list[LeavePolicyRuleUpsertIn] = Field(min_length=1)


class EmployeePolicyAssignIn(BaseModel):
    policy_id: UUID
    effective_from: date
    effective_to: date | None = None


class LeaveAllocationIn(BaseModel):
    employee_id: UUID
    leave_type_code: str = Field(min_length=1, max_length=64)
    year: int = Field(ge=1970, le=2100)
    days: float
    note: str | None = Field(default=None, max_length=2000)


class LeaveAllocationOut(BaseModel):
    ledger_id: UUID


class WeeklyOffDayIn(BaseModel):
    weekday: int = Field(ge=0, le=6)
    is_off: bool


class WeeklyOffPutIn(BaseModel):
    days: list[WeeklyOffDayIn] = Field(min_length=7, max_length=7)


class WeeklyOffOut(BaseModel):
    tenant_id: UUID
    branch_id: UUID
    days: list[WeeklyOffDayIn]


class HolidayCreateIn(BaseModel):
    day: date
    name: str = Field(min_length=1, max_length=200)
    branch_id: UUID | None = None


class HolidayOut(BaseModel):
    id: UUID
    tenant_id: UUID
    branch_id: UUID | None
    day: date
    name: str
    created_at: datetime


class HolidaysOut(BaseModel):
    items: list[HolidayOut]


class TeamLeaveSpanOut(BaseModel):
    leave_request_id: UUID
    employee_id: UUID
    start_date: date
    end_date: date
    leave_type_code: str
    requested_days: float


class TeamCalendarOut(BaseModel):
    items: list[TeamLeaveSpanOut]

