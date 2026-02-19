"""
FastAPI permission dependencies for onboarding v2 (Milestone 6).

These wrappers make routers easier to read and keep permission codes centralized
in app.auth.permissions.
"""

from __future__ import annotations

from fastapi import Depends

from app.auth.deps import require_permission
from app.auth.permissions import (
    ONBOARDING_BUNDLE_READ,
    ONBOARDING_BUNDLE_WRITE,
    ONBOARDING_TASK_READ,
    ONBOARDING_TASK_SUBMIT,
    ONBOARDING_TEMPLATE_READ,
    ONBOARDING_TEMPLATE_WRITE,
)
from app.shared.types import AuthContext


def require_onboarding_template_read(
    ctx: AuthContext = Depends(require_permission(ONBOARDING_TEMPLATE_READ)),
) -> AuthContext:
    return ctx


def require_onboarding_template_write(
    ctx: AuthContext = Depends(require_permission(ONBOARDING_TEMPLATE_WRITE)),
) -> AuthContext:
    return ctx


def require_onboarding_bundle_read(
    ctx: AuthContext = Depends(require_permission(ONBOARDING_BUNDLE_READ)),
) -> AuthContext:
    return ctx


def require_onboarding_bundle_write(
    ctx: AuthContext = Depends(require_permission(ONBOARDING_BUNDLE_WRITE)),
) -> AuthContext:
    return ctx


def require_onboarding_task_read(
    ctx: AuthContext = Depends(require_permission(ONBOARDING_TASK_READ)),
) -> AuthContext:
    return ctx


def require_onboarding_task_submit(
    ctx: AuthContext = Depends(require_permission(ONBOARDING_TASK_SUBMIT)),
) -> AuthContext:
    return ctx
