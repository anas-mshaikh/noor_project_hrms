from __future__ import annotations

"""
FastAPI dependencies for DMS permissions.

We keep these tiny wrappers so routers remain readable and permission codes are
centralized in `app.auth.permissions`.
"""

from fastapi import Depends

from app.auth.deps import require_permission
from app.auth.permissions import (
    DMS_DOCUMENT_READ,
    DMS_DOCUMENT_TYPE_READ,
    DMS_DOCUMENT_TYPE_WRITE,
    DMS_DOCUMENT_VERIFY,
    DMS_DOCUMENT_WRITE,
    DMS_EXPIRY_READ,
    DMS_EXPIRY_WRITE,
    DMS_FILE_READ,
    DMS_FILE_WRITE,
)
from app.shared.types import AuthContext


def require_dms_file_write(
    ctx: AuthContext = Depends(require_permission(DMS_FILE_WRITE)),
) -> AuthContext:
    return ctx


def require_dms_file_read(
    ctx: AuthContext = Depends(require_permission(DMS_FILE_READ)),
) -> AuthContext:
    return ctx


def require_dms_document_type_read(
    ctx: AuthContext = Depends(require_permission(DMS_DOCUMENT_TYPE_READ)),
) -> AuthContext:
    return ctx


def require_dms_document_type_write(
    ctx: AuthContext = Depends(require_permission(DMS_DOCUMENT_TYPE_WRITE)),
) -> AuthContext:
    return ctx


def require_dms_document_read(
    ctx: AuthContext = Depends(require_permission(DMS_DOCUMENT_READ)),
) -> AuthContext:
    return ctx


def require_dms_document_write(
    ctx: AuthContext = Depends(require_permission(DMS_DOCUMENT_WRITE)),
) -> AuthContext:
    return ctx


def require_dms_document_verify(
    ctx: AuthContext = Depends(require_permission(DMS_DOCUMENT_VERIFY)),
) -> AuthContext:
    return ctx


def require_dms_expiry_read(
    ctx: AuthContext = Depends(require_permission(DMS_EXPIRY_READ)),
) -> AuthContext:
    return ctx


def require_dms_expiry_write(
    ctx: AuthContext = Depends(require_permission(DMS_EXPIRY_WRITE)),
) -> AuthContext:
    return ctx
