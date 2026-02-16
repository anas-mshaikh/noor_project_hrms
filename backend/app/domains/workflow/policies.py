from __future__ import annotations

from fastapi import Depends

from app.auth.deps import get_auth_context, require_permission
from app.auth.permissions import (
    DMS_FILE_READ,
    WORKFLOW_DEFINITION_READ,
    WORKFLOW_DEFINITION_WRITE,
    WORKFLOW_REQUEST_ADMIN,
    WORKFLOW_REQUEST_APPROVE,
    WORKFLOW_REQUEST_READ,
    WORKFLOW_REQUEST_SUBMIT,
)
from app.core.errors import AppError
from app.shared.types import AuthContext


def require_workflow_request_read(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
    if WORKFLOW_REQUEST_READ in ctx.permissions or WORKFLOW_REQUEST_ADMIN in ctx.permissions:
        return ctx
    raise AppError(code="forbidden", message="Insufficient permission", status_code=403)


def require_workflow_request_submit(
    ctx: AuthContext = Depends(require_permission(WORKFLOW_REQUEST_SUBMIT)),
) -> AuthContext:
    return ctx


def require_workflow_request_approve(
    ctx: AuthContext = Depends(require_permission(WORKFLOW_REQUEST_APPROVE)),
) -> AuthContext:
    return ctx


def require_workflow_definition_read(
    ctx: AuthContext = Depends(require_permission(WORKFLOW_DEFINITION_READ)),
) -> AuthContext:
    return ctx


def require_workflow_definition_write(
    ctx: AuthContext = Depends(require_permission(WORKFLOW_DEFINITION_WRITE)),
) -> AuthContext:
    return ctx


def require_dms_file_read(ctx: AuthContext = Depends(require_permission(DMS_FILE_READ))) -> AuthContext:
    return ctx
