from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.auth.repo import list_role_assignments
from app.core.errors import AppError
from app.shared.types import Scope


def _parse_uuid_header(headers: dict[str, str], name: str, *, error_code: str) -> UUID | None:
    raw = headers.get(name)
    if not raw:
        return None
    try:
        return UUID(raw)
    except ValueError as e:
        raise AppError(code=error_code, message=f"Invalid {name}", status_code=400) from e


def _company_exists(db: Session, *, tenant_id: UUID, company_id: UUID) -> bool:
    return (
        db.execute(
            sa.text("SELECT 1 FROM tenancy.companies WHERE id = :company_id AND tenant_id = :tenant_id"),
            {"tenant_id": tenant_id, "company_id": company_id},
        ).first()
        is not None
    )


def _branch_tenant_and_company(db: Session, *, branch_id: UUID) -> tuple[UUID, UUID] | None:
    row = db.execute(
        sa.text("SELECT tenant_id, company_id FROM tenancy.branches WHERE id = :branch_id"),
        {"branch_id": branch_id},
    ).first()
    if row is None:
        return None
    return row[0], row[1]


def _branch_exists_in_company(db: Session, *, tenant_id: UUID, company_id: UUID, branch_id: UUID) -> bool:
    return (
        db.execute(
            sa.text(
                """
                SELECT 1
                FROM tenancy.branches
                WHERE id = :branch_id
                  AND tenant_id = :tenant_id
                  AND company_id = :company_id
                """
            ),
            {"tenant_id": tenant_id, "company_id": company_id, "branch_id": branch_id},
        ).first()
        is not None
    )


def _allowed_for_company(
    assignments: list[tuple[UUID, UUID | None, UUID | None, str]],
    *,
    tenant_id: UUID,
    company_id: UUID,
) -> bool:
    # Company header is allowed if the user has *any* assignment that covers the company:
    # - tenant-wide (company_id is NULL)
    # - company-wide (company_id matches)
    # - branch-specific within that company (company_id matches)
    for t_id, c_id, _b_id, _role in assignments:
        if t_id != tenant_id:
            continue
        if c_id is None or c_id == company_id:
            return True
    return False


def _allowed_for_branch(
    assignments: list[tuple[UUID, UUID | None, UUID | None, str]],
    *,
    tenant_id: UUID,
    company_id: UUID,
    branch_id: UUID,
) -> bool:
    for t_id, c_id, b_id, _role in assignments:
        if t_id != tenant_id:
            continue
        if c_id is not None and c_id != company_id:
            continue
        if b_id is not None and b_id != branch_id:
            continue
        return True
    return False


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
    tenant_assignments = [a for a in assignments if a[0] == tenant_id]

    company_header = _parse_uuid_header(headers, "X-Company-Id", error_code="iam.scope.invalid_company")
    branch_header = _parse_uuid_header(headers, "X-Branch-Id", error_code="iam.scope.invalid_branch")

    # If a branch is provided without company_id, infer company_id from the branch.
    if branch_header is not None and company_header is None:
        info = _branch_tenant_and_company(db, branch_id=branch_header)
        if info is None:
            raise AppError(code="iam.scope.invalid_branch", message="Invalid X-Branch-Id", status_code=400)
        branch_tenant_id, inferred_company_id = info
        if branch_tenant_id != tenant_id:
            raise AppError(code="iam.scope.invalid_branch", message="Invalid X-Branch-Id", status_code=400)
        company_header = inferred_company_id

    # Validate referenced company/branch IDs exist (avoid "forbidden" for typos).
    if company_header is not None and not _company_exists(db, tenant_id=tenant_id, company_id=company_header):
        raise AppError(code="iam.scope.invalid_company", message="Invalid X-Company-Id", status_code=400)

    if branch_header is not None:
        if company_header is None:
            raise AppError(code="iam.scope.invalid_branch", message="X-Branch-Id requires a company context", status_code=400)
        if not _branch_exists_in_company(db, tenant_id=tenant_id, company_id=company_header, branch_id=branch_header):
            raise AppError(code="iam.scope.invalid_branch", message="Invalid X-Branch-Id", status_code=400)

    # Header hardening: reject scopes not covered by the user's role assignments.
    if company_header is not None and not _allowed_for_company(tenant_assignments, tenant_id=tenant_id, company_id=company_header):
        raise AppError(code="iam.scope.forbidden", message="Company scope not allowed", status_code=403)
    if branch_header is not None and not _allowed_for_branch(
        tenant_assignments, tenant_id=tenant_id, company_id=company_header, branch_id=branch_header
    ):
        raise AppError(code="iam.scope.forbidden", message="Branch scope not allowed", status_code=403)

    tenant_wide = any(a[1] is None and a[2] is None for a in tenant_assignments)
    explicit_company_ids = {a[1] for a in tenant_assignments if a[1] is not None}
    allowed_company_ids = _list_company_ids(db, tenant_id) if tenant_wide else sorted(explicit_company_ids, key=str)

    company_id = company_header if company_header is not None else (allowed_company_ids[0] if allowed_company_ids else None)

    # Branch resolution (requires active company)
    allowed_branch_ids: list[UUID] = []
    if company_id is not None:
        company_assignments = [a for a in tenant_assignments if (a[1] is None or a[1] == company_id)]
        company_wide = any(a[2] is None for a in company_assignments)
        explicit_branch_ids = {a[2] for a in company_assignments if a[2] is not None}
        allowed_branch_ids = _list_branch_ids(db, company_id) if company_wide else sorted(explicit_branch_ids, key=str)

    branch_id = branch_header if branch_header is not None else (allowed_branch_ids[0] if allowed_branch_ids else None)

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
