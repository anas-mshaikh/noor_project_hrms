from __future__ import annotations

from fastapi import Depends

from app.auth.deps import require_permission
from app.auth.permissions import IAM_USER_READ, IAM_USER_WRITE
from app.shared.types import AuthContext


def require_iam_write(ctx: AuthContext = Depends(require_permission(IAM_USER_WRITE))) -> AuthContext:
    return ctx


def require_iam_read(ctx: AuthContext = Depends(require_permission(IAM_USER_READ))) -> AuthContext:
    return ctx
