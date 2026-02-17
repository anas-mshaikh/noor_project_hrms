from __future__ import annotations

from fastapi import Depends

from app.auth.deps import require_permission
from app.auth.permissions import (
    LEAVE_ADMIN_READ,
    LEAVE_ALLOCATION_WRITE,
    LEAVE_BALANCE_READ,
    LEAVE_POLICY_READ,
    LEAVE_POLICY_WRITE,
    LEAVE_REQUEST_READ,
    LEAVE_REQUEST_SUBMIT,
    LEAVE_TEAM_READ,
    LEAVE_TYPE_READ,
    LEAVE_TYPE_WRITE,
)
from app.shared.types import AuthContext


def require_leave_type_read(ctx: AuthContext = Depends(require_permission(LEAVE_TYPE_READ))) -> AuthContext:
    return ctx


def require_leave_type_write(ctx: AuthContext = Depends(require_permission(LEAVE_TYPE_WRITE))) -> AuthContext:
    return ctx


def require_leave_policy_read(ctx: AuthContext = Depends(require_permission(LEAVE_POLICY_READ))) -> AuthContext:
    return ctx


def require_leave_policy_write(ctx: AuthContext = Depends(require_permission(LEAVE_POLICY_WRITE))) -> AuthContext:
    return ctx


def require_leave_allocation_write(ctx: AuthContext = Depends(require_permission(LEAVE_ALLOCATION_WRITE))) -> AuthContext:
    return ctx


def require_leave_balance_read(ctx: AuthContext = Depends(require_permission(LEAVE_BALANCE_READ))) -> AuthContext:
    return ctx


def require_leave_request_submit(ctx: AuthContext = Depends(require_permission(LEAVE_REQUEST_SUBMIT))) -> AuthContext:
    return ctx


def require_leave_request_read(ctx: AuthContext = Depends(require_permission(LEAVE_REQUEST_READ))) -> AuthContext:
    return ctx


def require_leave_team_read(ctx: AuthContext = Depends(require_permission(LEAVE_TEAM_READ))) -> AuthContext:
    return ctx


def require_leave_admin_read(ctx: AuthContext = Depends(require_permission(LEAVE_ADMIN_READ))) -> AuthContext:
    return ctx

