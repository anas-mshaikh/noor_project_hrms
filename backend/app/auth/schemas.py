from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class UserOut(BaseModel):
    id: UUID
    email: EmailStr
    status: str


class ScopeOut(BaseModel):
    tenant_id: UUID
    company_id: UUID | None
    branch_id: UUID | None
    allowed_tenant_ids: list[UUID] = []
    allowed_company_ids: list[UUID] = []
    allowed_branch_ids: list[UUID] = []


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserOut
    roles: list[str]
    scope: ScopeOut


class MeResponse(BaseModel):
    user: UserOut
    roles: list[str]
    scope: ScopeOut

