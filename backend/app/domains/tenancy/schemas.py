from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class BootstrapRequest(BaseModel):
    tenant_name: str = Field(min_length=1, max_length=200)
    company_name: str = Field(min_length=1, max_length=200)
    branch_name: str = Field(min_length=1, max_length=200)
    branch_code: str = Field(min_length=1, max_length=64)
    timezone: str = Field(default="Asia/Riyadh", max_length=64)
    currency_code: str = Field(default="SAR", max_length=8)

    admin_email: EmailStr
    admin_password: str = Field(min_length=1)


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    legal_name: str | None = Field(default=None, max_length=200)
    currency_code: str | None = Field(default=None, max_length=8)
    timezone: str | None = Field(default=None, max_length=64)


class CompanyOut(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    legal_name: str | None
    currency_code: str | None
    timezone: str | None
    status: str


class BranchCreate(BaseModel):
    company_id: UUID
    name: str = Field(min_length=1, max_length=200)
    code: str = Field(min_length=1, max_length=64)
    timezone: str | None = Field(default=None, max_length=64)
    address: dict[str, Any] = Field(default_factory=dict)


class BranchOut(BaseModel):
    id: UUID
    tenant_id: UUID
    company_id: UUID
    name: str
    code: str
    timezone: str | None
    address: dict[str, Any]
    status: str


class OrgUnitCreate(BaseModel):
    company_id: UUID
    branch_id: UUID | None = None
    parent_id: UUID | None = None
    name: str = Field(min_length=1, max_length=200)
    unit_type: str | None = Field(default=None, max_length=64)


class OrgUnitOut(BaseModel):
    id: UUID
    tenant_id: UUID
    company_id: UUID
    branch_id: UUID | None
    parent_id: UUID | None
    name: str
    unit_type: str | None


class OrgUnitNode(BaseModel):
    id: UUID
    name: str
    unit_type: str | None = None
    children: list["OrgUnitNode"] = []


class JobTitleCreate(BaseModel):
    company_id: UUID
    name: str = Field(min_length=1, max_length=200)


class JobTitleOut(BaseModel):
    id: UUID
    tenant_id: UUID
    company_id: UUID
    name: str


class GradeCreate(BaseModel):
    company_id: UUID
    name: str = Field(min_length=1, max_length=200)
    level: int | None = None


class GradeOut(BaseModel):
    id: UUID
    tenant_id: UUID
    company_id: UUID
    name: str
    level: int | None

