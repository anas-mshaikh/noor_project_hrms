from __future__ import annotations

from fastapi import Depends

from app.auth.deps import require_roles
from app.shared.types import AuthContext


def require_iam_write(ctx: AuthContext = Depends(require_roles(["ADMIN", "HR_ADMIN"]))) -> AuthContext:
    return ctx


def require_iam_read(ctx: AuthContext = Depends(require_roles(["ADMIN", "HR_ADMIN", "HR_MANAGER"]))) -> AuthContext:
    return ctx

