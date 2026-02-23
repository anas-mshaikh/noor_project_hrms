from __future__ import annotations

from fastapi import Depends

from app.auth.deps import require_permission
from app.auth.permissions import (
    ATTENDANCE_ADMIN_READ,
    ATTENDANCE_CORRECTION_READ,
    ATTENDANCE_CORRECTION_SUBMIT,
    ATTENDANCE_PAYABLE_ADMIN_READ,
    ATTENDANCE_PAYABLE_READ,
    ATTENDANCE_PAYABLE_RECOMPUTE,
    ATTENDANCE_PAYABLE_TEAM_READ,
    ATTENDANCE_PUNCH_READ,
    ATTENDANCE_PUNCH_SUBMIT,
    ATTENDANCE_SETTINGS_WRITE,
    ATTENDANCE_TEAM_READ,
    ATTENDANCE_TIME_READ,
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


def require_attendance_punch_submit(
    ctx: AuthContext = Depends(require_permission(ATTENDANCE_PUNCH_SUBMIT)),
) -> AuthContext:
    return ctx


def require_attendance_punch_read(
    ctx: AuthContext = Depends(require_permission(ATTENDANCE_PUNCH_READ)),
) -> AuthContext:
    return ctx


def require_attendance_time_read(
    ctx: AuthContext = Depends(require_permission(ATTENDANCE_TIME_READ)),
) -> AuthContext:
    return ctx


def require_attendance_settings_write(
    ctx: AuthContext = Depends(require_permission(ATTENDANCE_SETTINGS_WRITE)),
) -> AuthContext:
    return ctx


def require_attendance_payable_read(
    ctx: AuthContext = Depends(require_permission(ATTENDANCE_PAYABLE_READ)),
) -> AuthContext:
    """ESS: read own payable summaries."""

    return ctx


def require_attendance_payable_team_read(
    ctx: AuthContext = Depends(require_permission(ATTENDANCE_PAYABLE_TEAM_READ)),
) -> AuthContext:
    """MSS: read team payable summaries."""

    return ctx


def require_attendance_payable_admin_read(
    ctx: AuthContext = Depends(require_permission(ATTENDANCE_PAYABLE_ADMIN_READ)),
) -> AuthContext:
    """HR/admin: read payable summaries."""

    return ctx


def require_attendance_payable_recompute(
    ctx: AuthContext = Depends(require_permission(ATTENDANCE_PAYABLE_RECOMPUTE)),
) -> AuthContext:
    """HR/admin: trigger payable recompute."""

    return ctx
