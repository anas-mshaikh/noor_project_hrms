from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class MobileProvisionIn(BaseModel):
    """
    Admin request to provision mobile access for an employee.

    Notes:
    - Email/password is the MVP. If `temp_password` is omitted, the backend generates one.
    - `phone_number` support is included for future Firebase Phone Auth flows.
    """

    email: EmailStr | None = None
    phone_number: str | None = None
    role: str = Field(default="employee", description="employee|admin")
    temp_password: str | None = Field(
        default=None,
        description="Optional temporary password for email flow; if omitted, backend generates one.",
    )


class MobileProvisionOut(BaseModel):
    firebase_uid: str
    employee_id: str
    employee_code: str
    active: bool
    # Only returned when the backend generated a password (email flow).
    generated_password: str | None = None


class MobileRevokeOut(BaseModel):
    firebase_uid: str
    active: bool


class MobileResyncOut(BaseModel):
    firebase_uid: str
    resynced: bool


class MobileAccountListOut(BaseModel):
    """
    Admin response for listing mobile account mappings for a store.

    This lets the dashboard show, per employee:
    - whether mobile access is provisioned
    - the Firebase UID (for debugging/support)
    - active/revoked state
    """

    employee_id: str
    employee_code: str
    firebase_uid: str
    role: str
    active: bool
    created_at: str
    revoked_at: str | None = None
