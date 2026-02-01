from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.auth.repo import list_role_assignments
from app.core.errors import AppError
from app.shared.types import Scope


def _parse_uuid_header(headers: dict[str, str], name: str) -> UUID | None:
    raw = headers.get(name)
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError as e:
        raise AppError(code="invalid_scope", message=f"Invalid {name}", status_code=400) from e


def _list_company_ids(db: Session, tenant_id: UUID) -> list[UUID]:
    rows = db.execute(
        sa.text(
            "SELECT id FROM tenancy.companies WHERE tenant_id = :tenant_id ORDER BY created_at, id"
        ),
        {"tenant_id": tenant_id},
    ).all()
    return [r[0] for r in rows]


def _list_branch_ids(db: Session, company_id: UUID) -> list[UUID]:
    rows = db.execute(
        sa.text("SELECT id FROM tenancy.branches WHERE company_id = :company_id ORDER BY created_at, id"),
        {"company_id": company_id},
    ).all()
    return [r[0] for r in rows]


def resolve_scope(db: Session, *, user_id: UUID, headers: dict[str, str]) -> Scope:
    """
    Resolve active tenant/company/branch based on role assignments and optional headers.

    Headers supported:
    - X-Company-Id
    - X-Branch-Id

    TODO: Add an explicit tenant selection endpoint for multi-tenant users.
    """

    assignments = list_role_assignments(db, user_id=user_id)
    if not assignments:
        raise AppError(code="forbidden", message="User has no role assignments", status_code=403)

    allowed_tenant_ids = tuple(sorted({a[0] for a in assignments}, key=str))
    tenant_id = allowed_tenant_ids[0]

    # Company resolution
    company_header = _parse_uuid_header(headers, "X-Company-Id")
    tenant_assignments = [a for a in assignments if a[0] == tenant_id]

    tenant_wide = any(a[1] is None for a in tenant_assignments)
    explicit_company_ids = {a[1] for a in tenant_assignments if a[1] is not None}
    allowed_company_ids = _list_company_ids(db, tenant_id) if tenant_wide else sorted(explicit_company_ids, key=str)

    if company_header is not None:
        if company_header not in set(allowed_company_ids):
            raise AppError(code="invalid_scope", message="Company not allowed", status_code=403)
        company_id = company_header
    else:
        company_id = allowed_company_ids[0] if allowed_company_ids else None

    # Branch resolution (requires active company)
    branch_header = _parse_uuid_header(headers, "X-Branch-Id")
    allowed_branch_ids: list[UUID] = []
    if company_id is not None:
        company_assignments = [
            a
            for a in tenant_assignments
            if (a[1] is None or a[1] == company_id)
        ]
        company_wide = any(a[2] is None for a in company_assignments)
        explicit_branch_ids = {a[2] for a in company_assignments if a[2] is not None}
        allowed_branch_ids = _list_branch_ids(db, company_id) if company_wide else sorted(explicit_branch_ids, key=str)

    if branch_header is not None:
        if branch_header not in set(allowed_branch_ids):
            raise AppError(code="invalid_scope", message="Branch not allowed", status_code=403)
        branch_id = branch_header
    else:
        branch_id = allowed_branch_ids[0] if allowed_branch_ids else None

    return Scope(
        tenant_id=tenant_id,
        company_id=company_id,
        branch_id=branch_id,
        allowed_tenant_ids=allowed_tenant_ids,
        allowed_company_ids=tuple(allowed_company_ids),
        allowed_branch_ids=tuple(allowed_branch_ids),
    )


def roles_for_scope(
    *,
    assignments: list[tuple[UUID, UUID | None, UUID | None, str]],
    scope: Scope,
) -> tuple[str, ...]:
    """
    Filter role codes that apply to the active scope.
    """

    role_codes: set[str] = set()
    for tenant_id, company_id, branch_id, role_code in assignments:
        if tenant_id != scope.tenant_id:
            continue
        if scope.company_id is None:
            if company_id is not None:
                continue
        else:
            if company_id is not None and company_id != scope.company_id:
                continue

        if scope.branch_id is None:
            if branch_id is not None:
                continue
        else:
            if branch_id is not None and branch_id != scope.branch_id:
                continue

        role_codes.add(role_code)

    return tuple(sorted(role_codes))

