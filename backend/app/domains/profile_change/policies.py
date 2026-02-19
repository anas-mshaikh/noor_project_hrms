"""
FastAPI permission dependencies for HR profile change (Milestone 6).

We keep these wrappers small so:
- routers stay readable
- permission codes remain centralized in app.auth.permissions
"""

from __future__ import annotations

from fastapi import Depends

from app.auth.deps import require_permission
from app.auth.permissions import HR_PROFILE_CHANGE_READ, HR_PROFILE_CHANGE_SUBMIT
from app.shared.types import AuthContext


def require_profile_change_submit(
    ctx: AuthContext = Depends(require_permission(HR_PROFILE_CHANGE_SUBMIT)),
) -> AuthContext:
    """Require permission to submit profile change requests (ESS)."""

    return ctx


def require_profile_change_read(
    ctx: AuthContext = Depends(require_permission(HR_PROFILE_CHANGE_READ)),
) -> AuthContext:
    """Require permission to read profile change requests."""

    return ctx
