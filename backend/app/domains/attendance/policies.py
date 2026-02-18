from __future__ import annotations

from fastapi import Depends

from app.auth.deps import require_permission
from app.auth.permissions import (
    ATTENDANCE_ADMIN_READ,
    ATTENDANCE_CORRECTION_READ,
    ATTENDANCE_CORRECTION_SUBMIT,
    ATTENDANCE_TEAM_READ,
)
from app.shared.types import AuthContext


def require_attendance_correction_submit(
    ctx: AuthContext = Depends(require_permission(ATTENDANCE_CORRECTION_SUBMIT)),
) -> AuthContext:
    return ctx


def require_attendance_correction_read(
    ctx: AuthContext = Depends(require_permission(ATTENDANCE_CORRECTION_READ)),
) -> AuthContext:
    return ctx


def require_attendance_team_read(
    ctx: AuthContext = Depends(require_permission(ATTENDANCE_TEAM_READ)),
) -> AuthContext:
    return ctx


def require_attendance_admin_read(
    ctx: AuthContext = Depends(require_permission(ATTENDANCE_ADMIN_READ)),
) -> AuthContext:
    return ctx

