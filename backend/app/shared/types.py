from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


@dataclass(frozen=True)
class Scope:
    """
    Resolved active scope for the current request.

    - tenant_id is always present.
    - company_id / branch_id are optional (based on user role assignments).
    """

    tenant_id: UUID
    company_id: UUID | None
    branch_id: UUID | None

    # For UI/debug: what the user is allowed to select.
    allowed_tenant_ids: tuple[UUID, ...] = ()
    allowed_company_ids: tuple[UUID, ...] = ()
    allowed_branch_ids: tuple[UUID, ...] = ()


@dataclass(frozen=True)
class AuthContext:
    user_id: UUID
    email: str
    status: str
    roles: tuple[str, ...]
    scope: Scope
    # Permission codes effective for the active scope (tenant/company/branch).
    permissions: frozenset[str] = frozenset()
    # Request correlation id (from X-Correlation-Id / generated in middleware).
    correlation_id: str | None = None
