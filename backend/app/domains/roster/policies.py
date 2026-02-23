"""
Roster RBAC policy dependencies (Milestone 8).

We keep these small wrapper dependencies so routers read cleanly and RBAC rules
stay centralized per domain.
"""

from __future__ import annotations

from fastapi import Depends

from app.auth.deps import require_permission
from app.auth.permissions import (
    ROSTER_ASSIGNMENT_READ,
    ROSTER_ASSIGNMENT_WRITE,
    ROSTER_DEFAULTS_WRITE,
    ROSTER_OVERRIDE_READ,
    ROSTER_OVERRIDE_WRITE,
    ROSTER_SHIFT_READ,
    ROSTER_SHIFT_WRITE,
)
from app.shared.types import AuthContext


def require_roster_shift_read(
    ctx: AuthContext = Depends(require_permission(ROSTER_SHIFT_READ)),
) -> AuthContext:
    return ctx


def require_roster_shift_write(
    ctx: AuthContext = Depends(require_permission(ROSTER_SHIFT_WRITE)),
) -> AuthContext:
    return ctx


def require_roster_defaults_write(
    ctx: AuthContext = Depends(require_permission(ROSTER_DEFAULTS_WRITE)),
) -> AuthContext:
    return ctx


def require_roster_assignment_read(
    ctx: AuthContext = Depends(require_permission(ROSTER_ASSIGNMENT_READ)),
) -> AuthContext:
    return ctx


def require_roster_assignment_write(
    ctx: AuthContext = Depends(require_permission(ROSTER_ASSIGNMENT_WRITE)),
) -> AuthContext:
    return ctx


def require_roster_override_read(
    ctx: AuthContext = Depends(require_permission(ROSTER_OVERRIDE_READ)),
) -> AuthContext:
    return ctx


def require_roster_override_write(
    ctx: AuthContext = Depends(require_permission(ROSTER_OVERRIDE_WRITE)),
) -> AuthContext:
    return ctx

