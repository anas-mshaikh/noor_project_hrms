from __future__ import annotations

from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.domains.tenancy.models import Branch, Company, Grade, JobTitle, OrgUnit, Tenant


def count_tenants(db: Session) -> int:
    return int(db.execute(sa.select(sa.func.count()).select_from(Tenant)).scalar() or 0)


def get_company(db: Session, *, company_id: UUID, tenant_id: UUID) -> Company | None:
    stmt = sa.select(Company).where(Company.id == company_id, Company.tenant_id == tenant_id)
    return db.execute(stmt).scalars().first()


def get_branch(db: Session, *, branch_id: UUID, tenant_id: UUID) -> Branch | None:
    stmt = sa.select(Branch).where(Branch.id == branch_id, Branch.tenant_id == tenant_id)
    return db.execute(stmt).scalars().first()


def insert_tenant(db: Session, *, tenant_id: UUID, name: str) -> Tenant:
    t = Tenant(id=tenant_id, name=name, status="ACTIVE")
    db.add(t)
    return t


def insert_company(
    db: Session,
    *,
    company_id: UUID,
    tenant_id: UUID,
    name: str,
    legal_name: str | None,
    currency_code: str | None,
    timezone: str | None,
) -> Company:
    c = Company(
        id=company_id,
        tenant_id=tenant_id,
        name=name,
        legal_name=legal_name,
        currency_code=currency_code,
        timezone=timezone,
        status="ACTIVE",
    )
    db.add(c)
    return c


def insert_branch(
    db: Session,
    *,
    branch_id: UUID,
    tenant_id: UUID,
    company_id: UUID,
    name: str,
    code: str,
    timezone: str | None,
    address: dict,
) -> Branch:
    b = Branch(
        id=branch_id,
        tenant_id=tenant_id,
        company_id=company_id,
        name=name,
        code=code,
        timezone=timezone,
        address=address,
        status="ACTIVE",
    )
    db.add(b)
    return b


def list_companies(db: Session, *, tenant_id: UUID) -> list[Company]:
    stmt = sa.select(Company).where(Company.tenant_id == tenant_id).order_by(Company.created_at, Company.id)
    return list(db.execute(stmt).scalars().all())


def list_branches(db: Session, *, tenant_id: UUID, company_id: UUID | None) -> list[Branch]:
    stmt = sa.select(Branch).where(Branch.tenant_id == tenant_id)
    if company_id is not None:
        stmt = stmt.where(Branch.company_id == company_id)
    stmt = stmt.order_by(Branch.created_at, Branch.id)
    return list(db.execute(stmt).scalars().all())


def list_org_units(
    db: Session,
    *,
    tenant_id: UUID,
    company_id: UUID,
    branch_id: UUID | None,
) -> list[OrgUnit]:
    stmt = sa.select(OrgUnit).where(OrgUnit.tenant_id == tenant_id, OrgUnit.company_id == company_id)
    if branch_id is not None:
        stmt = stmt.where(OrgUnit.branch_id == branch_id)
    stmt = stmt.order_by(OrgUnit.name, OrgUnit.id)
    return list(db.execute(stmt).scalars().all())


def insert_org_unit(
    db: Session,
    *,
    org_unit_id: UUID,
    tenant_id: UUID,
    company_id: UUID,
    branch_id: UUID | None,
    parent_id: UUID | None,
    name: str,
    unit_type: str | None,
) -> OrgUnit:
    ou = OrgUnit(
        id=org_unit_id,
        tenant_id=tenant_id,
        company_id=company_id,
        branch_id=branch_id,
        parent_id=parent_id,
        name=name,
        unit_type=unit_type,
    )
    db.add(ou)
    return ou


def list_job_titles(db: Session, *, tenant_id: UUID, company_id: UUID) -> list[JobTitle]:
    stmt = (
        sa.select(JobTitle)
        .where(JobTitle.tenant_id == tenant_id, JobTitle.company_id == company_id)
        .order_by(JobTitle.name, JobTitle.id)
    )
    return list(db.execute(stmt).scalars().all())


def insert_job_title(
    db: Session, *, job_title_id: UUID, tenant_id: UUID, company_id: UUID, name: str
) -> JobTitle:
    jt = JobTitle(id=job_title_id, tenant_id=tenant_id, company_id=company_id, name=name)
    db.add(jt)
    return jt


def list_grades(db: Session, *, tenant_id: UUID, company_id: UUID) -> list[Grade]:
    stmt = (
        sa.select(Grade)
        .where(Grade.tenant_id == tenant_id, Grade.company_id == company_id)
        .order_by(Grade.level.nullslast(), Grade.name, Grade.id)
    )
    return list(db.execute(stmt).scalars().all())


def insert_grade(
    db: Session,
    *,
    grade_id: UUID,
    tenant_id: UUID,
    company_id: UUID,
    name: str,
    level: int | None,
) -> Grade:
    g = Grade(id=grade_id, tenant_id=tenant_id, company_id=company_id, name=name, level=level)
    db.add(g)
    return g

