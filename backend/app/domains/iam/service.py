from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.passwords import hash_password, validate_password_strength
from app.auth.repo import list_role_assignments
from app.core.errors import AppError
from app.domains.iam import repo
from app.domains.iam.schemas import RoleAssignIn, UserCreateIn, UserPatchIn
from app.shared.types import AuthContext


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _actor_covers_scope(
    assignments: list[tuple[UUID, UUID | None, UUID | None, str]],
    *,
    tenant_id: UUID,
    company_id: UUID | None,
    branch_id: UUID | None,
) -> bool:
    """
    Returns True if the actor has at least one role assignment that covers the
    target scope (nulls mean wider scope).
    """

    for t_id, c_id, b_id, _role_code in assignments:
        if t_id != tenant_id:
            continue

        # Company dimension
        if company_id is None:
            if c_id is not None:
                continue
        else:
            if c_id is not None and c_id != company_id:
                continue

        # Branch dimension
        if branch_id is None:
            if b_id is not None:
                continue
        else:
            if b_id is not None and b_id != branch_id:
                continue

        return True

    return False


class IAMService:
    def create_user(self, db: Session, *, ctx: AuthContext, payload: UserCreateIn):
        email = str(payload.email)

        if repo.get_user_by_email(db, email=email) is not None:
            raise AppError(code="iam.user.email_exists", message="Email already exists", status_code=409)

        try:
            validate_password_strength(payload.password)
        except ValueError as e:
            raise AppError(code="iam.user.invalid_password", message=str(e), status_code=400) from e

        user = repo.create_user(
            db,
            email=email,
            phone=payload.phone,
            password_hash=hash_password(payload.password),
            status=payload.status,
        )

        # Ensure tenant membership by assigning the default EMPLOYEE role in the active scope.
        emp_role = repo.get_role_by_code(db, role_code="EMPLOYEE")
        if emp_role is None:
            raise AppError(code="iam.role.not_found", message="Missing IAM role EMPLOYEE", status_code=500)

        repo.create_user_role(
            db,
            user_id=user.id,
            tenant_id=ctx.scope.tenant_id,
            company_id=ctx.scope.company_id,
            branch_id=ctx.scope.branch_id,
            role_id=emp_role.id,
        )

        db.commit()
        db.refresh(user)
        return user

    def list_users(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        q: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ):
        return repo.list_users_for_tenant(
            db,
            tenant_id=ctx.scope.tenant_id,
            q=q,
            status=status,
            limit=limit,
            offset=offset,
        )

    def get_user(self, db: Session, *, ctx: AuthContext, user_id: UUID):
        user = repo.get_user_for_tenant(db, tenant_id=ctx.scope.tenant_id, user_id=user_id)
        if user is None:
            raise AppError(code="iam.user.not_found", message="User not found", status_code=404)
        return user

    def patch_user(self, db: Session, *, ctx: AuthContext, user_id: UUID, payload: UserPatchIn):
        user = self.get_user(db, ctx=ctx, user_id=user_id)

        repo.update_user_status_phone(db, user=user, status=payload.status, phone=payload.phone)

        if payload.status == "DISABLED":
            repo.revoke_refresh_tokens_for_user(db, user_id=user.id, now=_now())

        db.commit()
        db.refresh(user)
        return user

    def assign_role(self, db: Session, *, ctx: AuthContext, user_id: UUID, payload: RoleAssignIn):
        # Ensure target user is in tenant.
        if repo.get_user_for_tenant(db, tenant_id=ctx.scope.tenant_id, user_id=user_id) is None:
            raise AppError(code="iam.user.not_found", message="User not found", status_code=404)

        tenant_id = payload.tenant_id or ctx.scope.tenant_id
        if tenant_id != ctx.scope.tenant_id:
            raise AppError(code="iam.scope.forbidden", message="Cannot assign roles across tenants", status_code=403)

        company_id = payload.company_id
        branch_id = payload.branch_id

        if branch_id is not None and company_id is None:
            branch_info = repo.get_branch_company(db, branch_id=branch_id)
            if branch_info is None:
                raise AppError(code="iam.scope.invalid_branch", message="Invalid branch_id", status_code=400)
            branch_tenant_id, inferred_company_id = branch_info
            if branch_tenant_id != tenant_id:
                raise AppError(code="iam.scope.invalid_branch", message="Invalid branch_id", status_code=400)
            company_id = inferred_company_id

        if company_id is not None and not repo.validate_company_in_tenant(db, tenant_id=tenant_id, company_id=company_id):
            raise AppError(code="iam.scope.invalid_company", message="Invalid company_id", status_code=400)

        if branch_id is not None:
            if company_id is None:
                raise AppError(code="iam.scope.invalid_branch", message="branch_id requires company_id", status_code=400)
            if not repo.validate_branch_in_company(db, company_id=company_id, branch_id=branch_id):
                raise AppError(code="iam.scope.invalid_branch", message="Invalid branch_id", status_code=400)

        role = repo.get_role_by_code(db, role_code=payload.role_code)
        if role is None:
            raise AppError(code="iam.role.not_found", message="Role not found", status_code=404)

        assignments = list_role_assignments(db, user_id=ctx.user_id)
        if not _actor_covers_scope(assignments, tenant_id=tenant_id, company_id=company_id, branch_id=branch_id):
            raise AppError(code="iam.scope.forbidden", message="Scope not allowed", status_code=403)

        try:
            ur = repo.create_user_role(
                db,
                user_id=user_id,
                tenant_id=tenant_id,
                company_id=company_id,
                branch_id=branch_id,
                role_id=role.id,
            )
            db.commit()
            db.refresh(ur)
        except IntegrityError as e:
            db.rollback()
            raise AppError(code="iam.user_role.duplicate", message="Role assignment already exists", status_code=409) from e

        return ur, role.code

    def list_user_roles(self, db: Session, *, ctx: AuthContext, user_id: UUID):
        if repo.get_user_for_tenant(db, tenant_id=ctx.scope.tenant_id, user_id=user_id) is None:
            raise AppError(code="iam.user.not_found", message="User not found", status_code=404)
        return repo.list_user_roles(db, user_id=user_id, tenant_id=ctx.scope.tenant_id)

    def remove_role(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        user_id: UUID,
        role_code: str,
        company_id: UUID | None,
        branch_id: UUID | None,
    ) -> None:
        if repo.get_user_for_tenant(db, tenant_id=ctx.scope.tenant_id, user_id=user_id) is None:
            raise AppError(code="iam.user.not_found", message="User not found", status_code=404)

        if branch_id is not None and company_id is None:
            branch_info = repo.get_branch_company(db, branch_id=branch_id)
            if branch_info is None:
                raise AppError(code="iam.scope.invalid_branch", message="Invalid branch_id", status_code=400)
            branch_tenant_id, inferred_company_id = branch_info
            if branch_tenant_id != ctx.scope.tenant_id:
                raise AppError(code="iam.scope.invalid_branch", message="Invalid branch_id", status_code=400)
            company_id = inferred_company_id

        role = repo.get_role_by_code(db, role_code=role_code)
        if role is None:
            raise AppError(code="iam.role.not_found", message="Role not found", status_code=404)

        assignments = list_role_assignments(db, user_id=ctx.user_id)
        if not _actor_covers_scope(assignments, tenant_id=ctx.scope.tenant_id, company_id=company_id, branch_id=branch_id):
            raise AppError(code="iam.scope.forbidden", message="Scope not allowed", status_code=403)

        deleted = repo.delete_user_role(
            db,
            user_id=user_id,
            tenant_id=ctx.scope.tenant_id,
            role_id=role.id,
            company_id=company_id,
            branch_id=branch_id,
        )
        if deleted == 0:
            raise AppError(code="iam.user_role.not_found", message="Role assignment not found", status_code=404)
        db.commit()

    def list_roles(self, db: Session):
        return repo.list_roles(db)

    def list_permissions(self, db: Session):
        return repo.list_permissions(db)

