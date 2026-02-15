from __future__ import annotations

from uuid import UUID

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth import repo
from app.auth.jwt import decode_token
from app.auth.rbac import get_permissions
from app.auth.scope import resolve_scope, roles_for_scope
from app.core.errors import AppError
from app.db.session import get_db
from app.shared.types import AuthContext

_bearer = HTTPBearer(auto_error=False)


def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> UUID:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise AppError(code="unauthorized", message="Missing bearer token", status_code=401)
    try:
        claims = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError as e:
        raise AppError(code="unauthorized", message="Access token expired", status_code=401) from e
    except jwt.InvalidTokenError as e:
        raise AppError(code="unauthorized", message="Invalid access token", status_code=401) from e

    try:
        return UUID(str(claims["sub"]))
    except Exception as e:  # noqa: BLE001 - defensive
        raise AppError(code="unauthorized", message="Invalid access token subject", status_code=401) from e


def get_auth_context(
    request: Request,
    db: Session = Depends(get_db),
    user_id: UUID = Depends(get_current_user_id),
) -> AuthContext:
    user = repo.get_user_by_id(db, user_id=user_id)
    if user is None or user.status != "ACTIVE" or user.deleted_at is not None:
        raise AppError(code="unauthorized", message="User is disabled", status_code=401)

    # Scope selection uses role assignments and optional headers.
    #
    # For branch-first APIs we treat `{tenant_id}/{company_id}/{branch_id}` path params
    # as authoritative scope selectors. This keeps permission evaluation aligned with
    # the resource being accessed without requiring duplicate headers.
    hdrs = dict(request.headers)
    for param, header in (
        ("tenant_id", "X-Tenant-Id"),
        ("company_id", "X-Company-Id"),
        ("branch_id", "X-Branch-Id"),
    ):
        if param not in request.path_params:
            continue
        raw = str(request.path_params[param])
        existing = hdrs.get(header) or hdrs.get(header.lower())
        if existing and existing != raw:
            raise AppError(
                code="iam.scope.mismatch",
                message=f"{header} header does not match path parameter",
                status_code=400,
            )
        hdrs[header] = raw

    scope = resolve_scope(db, user_id=user.id, headers=hdrs)
    assignments = repo.list_role_assignments(db, user_id=user.id)
    roles = roles_for_scope(assignments=assignments, scope=scope)
    permissions = get_permissions(db, user_id=user.id, scope=scope)

    correlation_id = getattr(request.state, "correlation_id", None) or getattr(request.state, "trace_id", None)
    ctx = AuthContext(
        user_id=user.id,
        email=user.email,
        status=user.status,
        roles=roles,
        scope=scope,
        permissions=permissions,
        correlation_id=correlation_id,
    )
    request.state.user_id = str(user.id)
    request.state.scope = scope
    return ctx


def require_roles(required: list[str]):
    """
    Require at least one of the role codes in `required`.

    Example:
        Depends(require_roles(["ADMIN", "HR_MANAGER"]))
    """

    required_set = set(required)

    def _dep(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if not (set(ctx.roles) & required_set):
            raise AppError(code="forbidden", message="Insufficient role", status_code=403)
        return ctx

    return _dep


def require_permission(required: str):
    """
    Require a single permission code (permission-driven RBAC).

    Example:
        Depends(require_permission("iam:user:read"))
    """

    def _dep(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if required not in ctx.permissions:
            raise AppError(code="forbidden", message="Insufficient permission", status_code=403)
        return ctx

    return _dep


def rate_limit_placeholder() -> None:
    # TODO: add a real rate limiter (e.g., Redis-backed token bucket) before production.
    return None
