from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


UserStatus = Literal["ACTIVE", "DISABLED"]


class UserCreateIn(BaseModel):
    email: EmailStr
    phone: str | None = Field(default=None, max_length=32)
    password: str = Field(min_length=1)
    status: UserStatus = "ACTIVE"


class UserPatchIn(BaseModel):
    phone: str | None = Field(default=None, max_length=32)
    status: UserStatus | None = None


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    phone: str | None
    status: UserStatus
    created_at: datetime


class RoleAssignIn(BaseModel):
    role_code: str = Field(min_length=1, max_length=64)
    tenant_id: UUID | None = None
    company_id: UUID | None = None
    branch_id: UUID | None = None


class UserRoleOut(BaseModel):
    role_code: str
    tenant_id: UUID
    company_id: UUID | None
    branch_id: UUID | None
    created_at: datetime


class RoleOut(BaseModel):
    code: str
    name: str
    description: str | None = None


class PermissionOut(BaseModel):
    code: str
    description: str | None = None

