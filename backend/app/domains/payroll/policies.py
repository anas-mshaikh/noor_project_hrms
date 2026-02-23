"""
Payroll RBAC policy dependencies (Milestone 9).

We keep small wrapper dependencies so routers remain readable and domain RBAC
rules stay centralized.
"""

from __future__ import annotations

from fastapi import Depends

from app.auth.deps import require_permission
from app.auth.permissions import (
    PAYROLL_ADMIN_READ,
    PAYROLL_CALENDAR_READ,
    PAYROLL_CALENDAR_WRITE,
    PAYROLL_COMPENSATION_READ,
    PAYROLL_COMPENSATION_WRITE,
    PAYROLL_COMPONENT_READ,
    PAYROLL_COMPONENT_WRITE,
    PAYROLL_PAYRUN_EXPORT,
    PAYROLL_PAYRUN_GENERATE,
    PAYROLL_PAYRUN_PUBLISH,
    PAYROLL_PAYRUN_READ,
    PAYROLL_PAYRUN_SUBMIT,
    PAYROLL_PAYSLIP_PUBLISH,
    PAYROLL_PAYSLIP_READ,
    PAYROLL_STRUCTURE_READ,
    PAYROLL_STRUCTURE_WRITE,
)
from app.shared.types import AuthContext


def require_payroll_calendar_read(
    ctx: AuthContext = Depends(require_permission(PAYROLL_CALENDAR_READ)),
) -> AuthContext:
    return ctx


def require_payroll_calendar_write(
    ctx: AuthContext = Depends(require_permission(PAYROLL_CALENDAR_WRITE)),
) -> AuthContext:
    return ctx


def require_payroll_component_read(
    ctx: AuthContext = Depends(require_permission(PAYROLL_COMPONENT_READ)),
) -> AuthContext:
    return ctx


def require_payroll_component_write(
    ctx: AuthContext = Depends(require_permission(PAYROLL_COMPONENT_WRITE)),
) -> AuthContext:
    return ctx


def require_payroll_structure_read(
    ctx: AuthContext = Depends(require_permission(PAYROLL_STRUCTURE_READ)),
) -> AuthContext:
    return ctx


def require_payroll_structure_write(
    ctx: AuthContext = Depends(require_permission(PAYROLL_STRUCTURE_WRITE)),
) -> AuthContext:
    return ctx


def require_payroll_compensation_read(
    ctx: AuthContext = Depends(require_permission(PAYROLL_COMPENSATION_READ)),
) -> AuthContext:
    return ctx


def require_payroll_compensation_write(
    ctx: AuthContext = Depends(require_permission(PAYROLL_COMPENSATION_WRITE)),
) -> AuthContext:
    return ctx


def require_payroll_payrun_generate(
    ctx: AuthContext = Depends(require_permission(PAYROLL_PAYRUN_GENERATE)),
) -> AuthContext:
    return ctx


def require_payroll_payrun_read(
    ctx: AuthContext = Depends(require_permission(PAYROLL_PAYRUN_READ)),
) -> AuthContext:
    return ctx


def require_payroll_payrun_submit(
    ctx: AuthContext = Depends(require_permission(PAYROLL_PAYRUN_SUBMIT)),
) -> AuthContext:
    return ctx


def require_payroll_payrun_publish(
    ctx: AuthContext = Depends(require_permission(PAYROLL_PAYRUN_PUBLISH)),
) -> AuthContext:
    return ctx


def require_payroll_payrun_export(
    ctx: AuthContext = Depends(require_permission(PAYROLL_PAYRUN_EXPORT)),
) -> AuthContext:
    return ctx


def require_payroll_payslip_read(
    ctx: AuthContext = Depends(require_permission(PAYROLL_PAYSLIP_READ)),
) -> AuthContext:
    return ctx


def require_payroll_payslip_publish(
    ctx: AuthContext = Depends(require_permission(PAYROLL_PAYSLIP_PUBLISH)),
) -> AuthContext:
    return ctx


def require_payroll_admin_read(
    ctx: AuthContext = Depends(require_permission(PAYROLL_ADMIN_READ)),
) -> AuthContext:
    return ctx

