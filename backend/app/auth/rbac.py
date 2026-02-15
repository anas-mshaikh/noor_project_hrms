from __future__ import annotations

import json
import logging
from uuid import UUID

import sqlalchemy as sa
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.shared.types import Scope

logger = logging.getLogger("app.rbac")

# Short TTL: we want permission changes to take effect quickly without requiring
# perfect cache busting.
PERM_CACHE_TTL_SEC = 120


def _redis_conn() -> Redis | None:
    try:
        return Redis.from_url(settings.redis_url)
    except Exception:
        return None


def _version_key(*, tenant_id: UUID, user_id: UUID) -> str:
    return f"permsver:{tenant_id}:{user_id}"


def _perms_key(*, scope: Scope, user_id: UUID, version: int) -> str:
    company = str(scope.company_id) if scope.company_id is not None else "none"
    branch = str(scope.branch_id) if scope.branch_id is not None else "none"
    return f"perms:{scope.tenant_id}:{company}:{branch}:{user_id}:{version}"


def _load_permission_version(r: Redis, *, tenant_id: UUID, user_id: UUID) -> int:
    raw = r.get(_version_key(tenant_id=tenant_id, user_id=user_id))
    if raw is None:
        return 1
    try:
        return int(raw)
    except Exception:
        return 1


def bump_permission_version(*, tenant_id: UUID, user_id: UUID) -> None:
    """
    Best-effort cache busting for permission evaluation.

    We bump a small per-user version counter; permission cache keys include it.
    """
    r = _redis_conn()
    if r is None:
        return
    try:
        r.incr(_version_key(tenant_id=tenant_id, user_id=user_id))
    except RedisError:
        return


def _compute_permissions(db: Session, *, user_id: UUID, scope: Scope) -> frozenset[str]:
    """
    Compute effective permissions for a user at the active scope.

    Scope semantics:
    - tenant_id always required
    - company_id/branch_id restrict which scoped assignments apply
    """
    where_parts = [
        "ur.user_id = :user_id",
        "ur.tenant_id = :tenant_id",
    ]
    params: dict[str, object] = {"user_id": user_id, "tenant_id": scope.tenant_id}

    if scope.company_id is None:
        where_parts.append("ur.company_id IS NULL")
    else:
        where_parts.append("(ur.company_id IS NULL OR ur.company_id = :company_id)")
        params["company_id"] = scope.company_id

    if scope.branch_id is None:
        where_parts.append("ur.branch_id IS NULL")
    else:
        where_parts.append("(ur.branch_id IS NULL OR ur.branch_id = :branch_id)")
        params["branch_id"] = scope.branch_id

    sql = sa.text(
        f"""
        SELECT DISTINCT p.code
        FROM iam.user_roles ur
        JOIN iam.role_permissions rp ON rp.role_id = ur.role_id
        JOIN iam.permissions p ON p.id = rp.permission_id
        WHERE {' AND '.join(where_parts)}
        ORDER BY p.code
        """
    )
    rows = db.execute(sql, params).all()
    return frozenset(str(r[0]) for r in rows)


def get_permissions(db: Session, *, user_id: UUID, scope: Scope) -> frozenset[str]:
    """
    Return effective permissions (best-effort cached in Redis).
    """
    r = _redis_conn()
    if r is None:
        return _compute_permissions(db, user_id=user_id, scope=scope)

    try:
        version = _load_permission_version(r, tenant_id=scope.tenant_id, user_id=user_id)
        cache_key = _perms_key(scope=scope, user_id=user_id, version=version)
        cached = r.get(cache_key)
        if cached is not None:
            try:
                codes = json.loads(cached.decode("utf-8"))
                if isinstance(codes, list):
                    return frozenset(str(c) for c in codes)
            except Exception:
                # Fall through to recompute.
                pass

        perms = _compute_permissions(db, user_id=user_id, scope=scope)
        r.setex(cache_key, PERM_CACHE_TTL_SEC, json.dumps(sorted(perms)))
        return perms
    except RedisError:
        return _compute_permissions(db, user_id=user_id, scope=scope)

