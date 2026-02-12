from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.auth.jwt import create_access_token, create_refresh_token
from app.auth.models import RefreshToken as RefreshTokenModel
from app.auth.models import Role as RoleModel
from app.auth.models import User as UserModel
from app.auth.models import UserRole as UserRoleModel
from app.auth.passwords import hash_password, validate_password_strength
from app.core.config import settings
from app.core.errors import AppError
from app.domains.tenancy import repo
from app.domains.tenancy.models import Branch, Company, Grade, JobTitle, OrgUnit, Tenant
from app.shared.types import AuthContext, Scope


@dataclass(frozen=True)
class BootstrapResult:
    access_token: str
    refresh_token: str
    ctx: AuthContext


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash_refresh_token(raw_refresh_token: str) -> str:
    raw = (raw_refresh_token + settings.auth_refresh_token_pepper).encode()
    return hashlib.sha256(raw).hexdigest()


class TenancyService:
    def bootstrap(
        self,
        db: Session,
        *,
        tenant_name: str,
        company_name: str,
        branch_name: str,
        branch_code: str,
        timezone_name: str,
        currency_code: str,
        admin_email: str,
        admin_password: str,
        ip: str | None,
        user_agent: str | None,
    ) -> BootstrapResult:
        if repo.count_tenants(db) > 0:
            raise AppError(
                code="already_bootstrapped",
                message="Bootstrap is only allowed on a fresh database",
                status_code=409,
            )

        try:
            validate_password_strength(admin_password)
        except ValueError as e:
            raise AppError(code="invalid_password", message=str(e), status_code=400) from e

        now = _now()
        tenant_id = uuid4()
        company_id = uuid4()
        branch_id = uuid4()
        user_id = uuid4()

        # Create tenant/company/branch
        repo.insert_tenant(db, tenant_id=tenant_id, name=tenant_name)
        db.flush()
        repo.insert_company(
            db,
            company_id=company_id,
            tenant_id=tenant_id,
            name=company_name,
            legal_name=company_name,
            currency_code=currency_code,
            timezone=timezone_name,
        )
        db.flush()
        repo.insert_branch(
            db,
            branch_id=branch_id,
            tenant_id=tenant_id,
            company_id=company_id,
            name=branch_name,
            code=branch_code,
            timezone=timezone_name,
            address={},
        )
        db.flush()

        # Create admin user
        user = UserModel(
            id=user_id,
            email=admin_email,
            phone=None,
            password_hash=hash_password(admin_password),
            status="ACTIVE",
            last_login_at=now,
        )
        db.add(user)
        # SessionLocal uses autoflush=False; flush now so dependent rows
        # (user_roles, refresh_tokens) cannot race this insert at commit time.
        db.flush()

        # Assign ADMIN role scoped to tenant/company/branch.
        admin_role_id = db.execute(
            sa.select(RoleModel.id).where(RoleModel.code == "ADMIN")
        ).scalar()
        if admin_role_id is None:
            raise AppError(code="bootstrap_failed", message="Missing IAM role ADMIN", status_code=500)

        db.add(
            UserRoleModel(
                user_id=user_id,
                tenant_id=tenant_id,
                company_id=company_id,
                branch_id=branch_id,
                role_id=admin_role_id,
            )
        )

        # Issue tokens (refresh is stored hashed).
        access_token = create_access_token(subject=str(user_id))
        refresh_token = create_refresh_token()
        db.add(
            RefreshTokenModel(
                user_id=user_id,
                token_hash=_hash_refresh_token(refresh_token),
                expires_at=now + timedelta(days=settings.auth_refresh_token_ttl_days),
                revoked_at=None,
                ip=ip,
                user_agent=user_agent,
            )
        )

        db.commit()

        scope = Scope(
            tenant_id=tenant_id,
            company_id=company_id,
            branch_id=branch_id,
            allowed_tenant_ids=(tenant_id,),
            allowed_company_ids=(company_id,),
            allowed_branch_ids=(branch_id,),
        )
        ctx = AuthContext(
            user_id=user_id,
            email=admin_email,
            status="ACTIVE",
            roles=("ADMIN",),
            scope=scope,
        )
        return BootstrapResult(access_token=access_token, refresh_token=refresh_token, ctx=ctx)

    def list_companies(self, db: Session, *, tenant_id: UUID) -> list[Company]:
        return repo.list_companies(db, tenant_id=tenant_id)

    def create_company(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        name: str,
        legal_name: str | None,
        currency_code: str | None,
        timezone_name: str | None,
    ) -> Company:
        company_id = uuid4()
        c = repo.insert_company(
            db,
            company_id=company_id,
            tenant_id=tenant_id,
            name=name,
            legal_name=legal_name,
            currency_code=currency_code,
            timezone=timezone_name,
        )
        db.commit()
        return c

    def list_branches(
        self, db: Session, *, tenant_id: UUID, company_id: UUID | None
    ) -> list[Branch]:
        return repo.list_branches(db, tenant_id=tenant_id, company_id=company_id)

    def create_branch(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        company_id: UUID,
        name: str,
        code: str,
        timezone_name: str | None,
        address: dict,
    ) -> Branch:
        if repo.get_company(db, company_id=company_id, tenant_id=tenant_id) is None:
            raise AppError(code="not_found", message="Company not found", status_code=404)
        b = repo.insert_branch(
            db,
            branch_id=uuid4(),
            tenant_id=tenant_id,
            company_id=company_id,
            name=name,
            code=code,
            timezone=timezone_name,
            address=address,
        )
        db.commit()
        return b

    def list_org_units(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        company_id: UUID,
        branch_id: UUID | None,
    ) -> list[OrgUnit]:
        if repo.get_company(db, company_id=company_id, tenant_id=tenant_id) is None:
            raise AppError(code="not_found", message="Company not found", status_code=404)
        if branch_id is not None and repo.get_branch(db, branch_id=branch_id, tenant_id=tenant_id) is None:
            raise AppError(code="not_found", message="Branch not found", status_code=404)
        return repo.list_org_units(db, tenant_id=tenant_id, company_id=company_id, branch_id=branch_id)

    def create_org_unit(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        company_id: UUID,
        branch_id: UUID | None,
        parent_id: UUID | None,
        name: str,
        unit_type: str | None,
    ) -> OrgUnit:
        if repo.get_company(db, company_id=company_id, tenant_id=tenant_id) is None:
            raise AppError(code="not_found", message="Company not found", status_code=404)
        if branch_id is not None and repo.get_branch(db, branch_id=branch_id, tenant_id=tenant_id) is None:
            raise AppError(code="not_found", message="Branch not found", status_code=404)

        ou = repo.insert_org_unit(
            db,
            org_unit_id=uuid4(),
            tenant_id=tenant_id,
            company_id=company_id,
            branch_id=branch_id,
            parent_id=parent_id,
            name=name,
            unit_type=unit_type,
        )
        db.commit()
        return ou

    def build_org_chart(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        company_id: UUID,
        branch_id: UUID | None,
    ) -> list[dict]:
        units = self.list_org_units(
            db,
            tenant_id=tenant_id,
            company_id=company_id,
            branch_id=branch_id,
        )
        by_parent: dict[UUID | None, list[OrgUnit]] = {}
        for u in units:
            by_parent.setdefault(u.parent_id, []).append(u)

        for siblings in by_parent.values():
            siblings.sort(key=lambda x: (x.name.lower(), str(x.id)))

        def build(parent_id: UUID | None) -> list[dict]:
            children = []
            for u in by_parent.get(parent_id, []):
                children.append(
                    {
                        "id": u.id,
                        "name": u.name,
                        "unit_type": u.unit_type,
                        "children": build(u.id),
                    }
                )
            return children

        return build(None)

    def list_job_titles(self, db: Session, *, tenant_id: UUID, company_id: UUID) -> list[JobTitle]:
        if repo.get_company(db, company_id=company_id, tenant_id=tenant_id) is None:
            raise AppError(code="not_found", message="Company not found", status_code=404)
        return repo.list_job_titles(db, tenant_id=tenant_id, company_id=company_id)

    def create_job_title(
        self, db: Session, *, tenant_id: UUID, company_id: UUID, name: str
    ) -> JobTitle:
        if repo.get_company(db, company_id=company_id, tenant_id=tenant_id) is None:
            raise AppError(code="not_found", message="Company not found", status_code=404)
        jt = repo.insert_job_title(db, job_title_id=uuid4(), tenant_id=tenant_id, company_id=company_id, name=name)
        db.commit()
        return jt

    def list_grades(self, db: Session, *, tenant_id: UUID, company_id: UUID) -> list[Grade]:
        if repo.get_company(db, company_id=company_id, tenant_id=tenant_id) is None:
            raise AppError(code="not_found", message="Company not found", status_code=404)
        return repo.list_grades(db, tenant_id=tenant_id, company_id=company_id)

    def create_grade(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        company_id: UUID,
        name: str,
        level: int | None,
    ) -> Grade:
        if repo.get_company(db, company_id=company_id, tenant_id=tenant_id) is None:
            raise AppError(code="not_found", message="Company not found", status_code=404)
        g = repo.insert_grade(
            db,
            grade_id=uuid4(),
            tenant_id=tenant_id,
            company_id=company_id,
            name=name,
            level=level,
        )
        db.commit()
        return g
