"""
Payroll Pydantic schemas (Milestone 9).

The v1 API is intentionally explicit and conservative:
- Money is represented as Decimal (serialized as JSON numbers/strings by FastAPI).
- Payloads avoid PII and avoid logging sensitive values in audits.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field


PayrollFrequency = Literal["MONTHLY"]
PeriodStatus = Literal["OPEN", "CLOSED"]
ComponentType = Literal["EARNING", "DEDUCTION"]
ComponentCalcMode = Literal["FIXED", "PERCENT_OF_GROSS", "MANUAL"]
PayrunStatus = Literal["DRAFT", "PENDING_APPROVAL", "APPROVED", "PUBLISHED", "CANCELED"]
PayrunItemStatus = Literal["INCLUDED", "EXCLUDED"]
PayslipStatus = Literal["READY", "PUBLISHED"]


# ------------------------------------------------------------------
# Calendars / periods
# ------------------------------------------------------------------


class PayrollCalendarCreateIn(BaseModel):
    """Create a payroll calendar (tenant-scoped)."""

    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    currency_code: str = Field(min_length=3, max_length=16)
    timezone: str = Field(min_length=1, max_length=64)
    is_active: bool = True


class PayrollCalendarOut(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    frequency: PayrollFrequency
    currency_code: str
    timezone: str
    is_active: bool
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


class PayrollPeriodCreateIn(BaseModel):
    """Create a period for a calendar (inclusive end_date)."""

    period_key: str = Field(min_length=7, max_length=7, description="Format: YYYY-MM")
    start_date: date
    end_date: date


class PayrollPeriodOut(BaseModel):
    id: UUID
    tenant_id: UUID
    calendar_id: UUID
    period_key: str
    start_date: date
    end_date: date
    status: PeriodStatus
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------
# Components / structures
# ------------------------------------------------------------------


class PayrollComponentCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    component_type: ComponentType
    calc_mode: ComponentCalcMode = "FIXED"
    default_amount: Decimal | None = Field(default=None)
    default_percent: Decimal | None = Field(default=None)
    is_taxable: bool = False
    is_active: bool = True


class PayrollComponentOut(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    component_type: ComponentType
    calc_mode: ComponentCalcMode
    default_amount: Decimal | None
    default_percent: Decimal | None
    is_taxable: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SalaryStructureCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    is_active: bool = True


class SalaryStructureOut(BaseModel):
    id: UUID
    tenant_id: UUID
    code: str
    name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


class SalaryStructureLineCreateIn(BaseModel):
    component_id: UUID
    sort_order: int = Field(ge=0, le=10_000)
    calc_mode_override: ComponentCalcMode | None = None
    amount_override: Decimal | None = None
    percent_override: Decimal | None = None


class SalaryStructureLineOut(BaseModel):
    id: UUID
    tenant_id: UUID
    salary_structure_id: UUID
    component_id: UUID
    sort_order: int
    calc_mode_override: ComponentCalcMode | None
    amount_override: Decimal | None
    percent_override: Decimal | None
    created_at: datetime


class SalaryStructureDetailOut(BaseModel):
    structure: SalaryStructureOut
    lines: list[SalaryStructureLineOut]


# ------------------------------------------------------------------
# Employee compensation
# ------------------------------------------------------------------


class EmployeeCompensationUpsertIn(BaseModel):
    currency_code: str = Field(min_length=3, max_length=16)
    salary_structure_id: UUID
    base_amount: Decimal = Field(gt=Decimal("0"))
    effective_from: date
    effective_to: date | None = None
    overrides_json: dict[str, Any] | None = None


class EmployeeCompensationOut(BaseModel):
    id: UUID
    tenant_id: UUID
    employee_id: UUID
    currency_code: str
    salary_structure_id: UUID
    base_amount: Decimal
    effective_from: date
    effective_to: date | None
    overrides_json: dict[str, Any] | None
    created_by_user_id: UUID | None
    created_at: datetime
    updated_at: datetime


# ------------------------------------------------------------------
# Payruns
# ------------------------------------------------------------------


class PayrunGenerateIn(BaseModel):
    calendar_id: UUID
    period_key: str = Field(min_length=7, max_length=7, description="Format: YYYY-MM")
    branch_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=200)


class PayrunOut(BaseModel):
    id: UUID
    tenant_id: UUID
    calendar_id: UUID
    period_id: UUID
    branch_id: UUID | None
    version: int
    status: PayrunStatus
    generated_at: datetime
    generated_by_user_id: UUID | None
    workflow_request_id: UUID | None
    idempotency_key: str | None
    totals_json: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


class PayrunItemOut(BaseModel):
    id: UUID
    tenant_id: UUID
    payrun_id: UUID
    employee_id: UUID
    payable_days: int
    payable_minutes: int
    working_days_in_period: int
    gross_amount: Decimal
    deductions_amount: Decimal
    net_amount: Decimal
    status: PayrunItemStatus
    computed_json: dict[str, Any]
    anomalies_json: dict[str, Any] | None
    created_at: datetime


class PayrunItemLineOut(BaseModel):
    id: UUID
    tenant_id: UUID
    payrun_item_id: UUID
    component_id: UUID
    component_code: str
    component_type: ComponentType
    amount: Decimal
    meta_json: dict[str, Any] | None
    created_at: datetime


class PayrunDetailOut(BaseModel):
    payrun: PayrunOut
    items: list[PayrunItemOut]
    lines: list[PayrunItemLineOut] | None = None


class PayrunSubmitApprovalOut(BaseModel):
    payrun_id: UUID
    workflow_request_id: UUID
    status: PayrunStatus


class PayrunPublishOut(BaseModel):
    payrun_id: UUID
    published_count: int
    status: PayrunStatus


# ------------------------------------------------------------------
# Payslips (ESS)
# ------------------------------------------------------------------


class PayslipOut(BaseModel):
    id: UUID
    tenant_id: UUID
    payrun_id: UUID
    employee_id: UUID
    status: PayslipStatus
    dms_document_id: UUID | None
    period_key: str | None = None
    created_at: datetime
    updated_at: datetime


class PayslipListOut(BaseModel):
    items: list[PayslipOut]

