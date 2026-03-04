from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session, aliased

from app.auth.models import User
from app.core.errors import AppError
from app.domains.hr_core.models import Employee, EmployeeEmployment, EmployeeUserLink, Person


@dataclass(frozen=True)
class ManagerSummary:
    employee_id: UUID
    display_name: str
    employee_code: str | None


@dataclass(frozen=True)
class LinkedUserSummary:
    user_id: UUID
    email: str
    status: str
    linked_at: datetime


@dataclass(frozen=True)
class Employee360Row:
    employee: Employee
    person: Person
    current_employment: EmployeeEmployment | None
    manager: ManagerSummary | None
    linked_user: LinkedUserSummary | None


@dataclass(frozen=True)
class EmployeeDirectoryRow:
    employee_id: UUID
    employee_code: str
    status: str
    full_name: str
    email: str | None
    phone: str | None
    branch_id: UUID | None
    org_unit_id: UUID | None
    manager_employee_id: UUID | None
    manager_name: str | None
    has_user_link: bool


def _current_employment_subquery() -> sa.Subquery:
    """
    Canonical "current employment" selection:
    - end_date IS NULL
    - prefer is_primary = TRUE when present
    - fallback to latest start_date

    Implemented with a window function to be deterministic and portable.
    """

    ee = EmployeeEmployment
    rn = sa.func.row_number().over(
        partition_by=ee.employee_id,
        order_by=(sa.desc(ee.is_primary).nulls_last(), ee.start_date.desc(), ee.id.desc()),
    ).label("rn")
    return (
        sa.select(
            ee.id.label("id"),
            ee.tenant_id.label("tenant_id"),
            ee.company_id.label("company_id"),
            ee.employee_id.label("employee_id"),
            ee.branch_id.label("branch_id"),
            ee.org_unit_id.label("org_unit_id"),
            ee.job_title_id.label("job_title_id"),
            ee.grade_id.label("grade_id"),
            ee.manager_employee_id.label("manager_employee_id"),
            ee.start_date.label("start_date"),
            ee.end_date.label("end_date"),
            ee.is_primary.label("is_primary"),
            ee.created_at.label("created_at"),
            ee.updated_at.label("updated_at"),
            rn,
        )
        .where(ee.end_date.is_(None))
        .subquery("current_employment")
    )


def get_current_employment(
    db: Session, *, tenant_id: UUID, company_id: UUID, employee_id: UUID
) -> EmployeeEmployment | None:
    stmt = (
        sa.select(EmployeeEmployment)
        .where(
            EmployeeEmployment.tenant_id == tenant_id,
            EmployeeEmployment.company_id == company_id,
            EmployeeEmployment.employee_id == employee_id,
            EmployeeEmployment.end_date.is_(None),
        )
        .order_by(sa.desc(EmployeeEmployment.is_primary).nulls_last(), EmployeeEmployment.start_date.desc(), EmployeeEmployment.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def employee_code_exists(db: Session, *, company_id: UUID, employee_code: str) -> bool:
    return (
        db.execute(
            sa.select(sa.literal(True))
            .select_from(Employee)
            .where(Employee.company_id == company_id, Employee.employee_code == employee_code)
            .limit(1)
        ).first()
        is not None
    )


def insert_person(
    db: Session,
    *,
    tenant_id: UUID,
    first_name: str,
    last_name: str,
    dob: date | None,
    nationality: str | None,
    email: str | None,
    phone: str | None,
    address: dict,
) -> Person:
    p = Person(
        id=uuid4(),
        tenant_id=tenant_id,
        first_name=first_name,
        last_name=last_name,
        dob=dob,
        nationality=nationality,
        email=email,
        phone=phone,
        address=address,
    )
    db.add(p)
    return p


def insert_employee(
    db: Session,
    *,
    tenant_id: UUID,
    company_id: UUID,
    person_id: UUID,
    employee_code: str,
    status: str,
    join_date: date | None,
    termination_date: date | None,
) -> Employee:
    e = Employee(
        id=uuid4(),
        tenant_id=tenant_id,
        company_id=company_id,
        person_id=person_id,
        employee_code=employee_code,
        status=status,
        join_date=join_date,
        termination_date=termination_date,
    )
    db.add(e)
    return e


def insert_employment(
    db: Session,
    *,
    tenant_id: UUID,
    company_id: UUID,
    employee_id: UUID,
    branch_id: UUID,
    org_unit_id: UUID | None,
    job_title_id: UUID | None,
    grade_id: UUID | None,
    manager_employee_id: UUID | None,
    start_date: date,
    end_date: date | None,
    is_primary: bool,
) -> EmployeeEmployment:
    ee = EmployeeEmployment(
        id=uuid4(),
        tenant_id=tenant_id,
        company_id=company_id,
        employee_id=employee_id,
        branch_id=branch_id,
        org_unit_id=org_unit_id,
        job_title_id=job_title_id,
        grade_id=grade_id,
        manager_employee_id=manager_employee_id,
        start_date=start_date,
        end_date=end_date,
        is_primary=is_primary,
    )
    db.add(ee)
    return ee


def get_employee_360_by_id(
    db: Session,
    *,
    tenant_id: UUID,
    company_id: UUID,
    employee_id: UUID,
) -> Employee360Row | None:
    stmt = (
        sa.select(Employee, Person)
        .join(Person, Person.id == Employee.person_id)
        .where(Employee.id == employee_id, Employee.tenant_id == tenant_id, Employee.company_id == company_id)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    employee: Employee = row[0]
    person: Person = row[1]

    current = get_current_employment(db, tenant_id=tenant_id, company_id=company_id, employee_id=employee_id)

    manager: ManagerSummary | None = None
    if current is not None and current.manager_employee_id is not None:
        mgr_stmt = (
            sa.select(Employee, Person)
            .join(Person, Person.id == Employee.person_id)
            .where(
                Employee.id == current.manager_employee_id,
                Employee.tenant_id == tenant_id,
                Employee.company_id == company_id,
            )
        )
        mgr_row = db.execute(mgr_stmt).first()
        if mgr_row is not None:
            mgr_emp: Employee = mgr_row[0]
            mgr_person: Person = mgr_row[1]
            display_name = f"{mgr_person.first_name} {mgr_person.last_name}".strip()
            manager = ManagerSummary(
                employee_id=mgr_emp.id,
                display_name=display_name,
                employee_code=mgr_emp.employee_code,
            )

    linked_user: LinkedUserSummary | None = None
    link_row = db.execute(
        sa.select(EmployeeUserLink, User)
        .join(User, User.id == EmployeeUserLink.user_id)
        .where(EmployeeUserLink.employee_id == employee_id, User.deleted_at.is_(None))
        .limit(1)
    ).first()
    if link_row is not None:
        link: EmployeeUserLink = link_row[0]
        user: User = link_row[1]
        linked_user = LinkedUserSummary(
            user_id=user.id,
            email=user.email,
            status=user.status,
            linked_at=link.created_at,
        )

    return Employee360Row(
        employee=employee,
        person=person,
        current_employment=current,
        manager=manager,
        linked_user=linked_user,
    )


def list_employees_directory(
    db: Session,
    *,
    tenant_id: UUID,
    company_id: UUID,
    q: str | None,
    status: str | None,
    branch_id: UUID | None,
    org_unit_id: UUID | None,
    limit: int,
    offset: int,
) -> tuple[list[EmployeeDirectoryRow], int]:
    ce = _current_employment_subquery()
    mgr_emp = aliased(Employee, name="mgr_emp")
    mgr_person = aliased(Person, name="mgr_person")

    filters: list[sa.ColumnElement[bool]] = [Employee.tenant_id == tenant_id, Employee.company_id == company_id]

    if status:
        filters.append(Employee.status == status)

    if q:
        like = f"%{q}%"
        filters.append(
            sa.or_(
                Employee.employee_code.ilike(like),
                Person.first_name.ilike(like),
                Person.last_name.ilike(like),
                Person.email.ilike(like),
                Person.phone.ilike(like),
            )
        )

    if branch_id is not None:
        filters.append(ce.c.branch_id == branch_id)
        filters.append(ce.c.rn == 1)

    if org_unit_id is not None:
        filters.append(ce.c.org_unit_id == org_unit_id)
        filters.append(ce.c.rn == 1)

    has_user_link = sa.exists(
        sa.select(1)
        .select_from(EmployeeUserLink)
        .where(EmployeeUserLink.employee_id == Employee.id)
    ).label("has_user_link")

    base = (
        sa.select(
            Employee.id.label("employee_id"),
            Employee.employee_code.label("employee_code"),
            Employee.status.label("status"),
            Person.first_name.label("first_name"),
            Person.last_name.label("last_name"),
            Person.email.label("email"),
            Person.phone.label("phone"),
            ce.c.branch_id.label("branch_id"),
            ce.c.org_unit_id.label("org_unit_id"),
            ce.c.manager_employee_id.label("manager_employee_id"),
            mgr_person.first_name.label("mgr_first_name"),
            mgr_person.last_name.label("mgr_last_name"),
            has_user_link,
        )
        .select_from(Employee)
        .join(Person, Person.id == Employee.person_id)
        .outerjoin(ce, sa.and_(ce.c.employee_id == Employee.id, ce.c.rn == 1))
        .outerjoin(mgr_emp, mgr_emp.id == ce.c.manager_employee_id)
        .outerjoin(mgr_person, mgr_person.id == mgr_emp.person_id)
        .where(*filters)
    )

    base_sq = base.subquery("employees_directory")
    total = int(db.execute(sa.select(sa.func.count(sa.distinct(base_sq.c.employee_id)))).scalar() or 0)

    stmt = (
        base.order_by(Employee.employee_code.asc(), Employee.created_at.desc(), Employee.id.desc())
        .limit(limit)
        .offset(offset)
    )

    items: list[EmployeeDirectoryRow] = []
    for r in db.execute(stmt).all():
        full_name = f"{r.first_name} {r.last_name}".strip()
        mgr_name = None
        if r.mgr_first_name is not None or r.mgr_last_name is not None:
            mgr_name = f"{r.mgr_first_name or ''} {r.mgr_last_name or ''}".strip()

        items.append(
            EmployeeDirectoryRow(
                employee_id=r.employee_id,
                employee_code=r.employee_code,
                status=r.status,
                full_name=full_name,
                email=r.email,
                phone=r.phone,
                branch_id=r.branch_id,
                org_unit_id=r.org_unit_id,
                manager_employee_id=r.manager_employee_id,
                manager_name=mgr_name,
                has_user_link=bool(r.has_user_link),
            )
        )

    return items, total


def get_employee_id_by_user_id(db: Session, *, user_id: UUID) -> tuple[UUID, UUID, UUID] | None:
    stmt = (
        sa.select(Employee.id, Employee.tenant_id, Employee.company_id)
        .select_from(EmployeeUserLink)
        .join(Employee, Employee.id == EmployeeUserLink.employee_id)
        .where(EmployeeUserLink.user_id == user_id)
    )
    row = db.execute(stmt).first()
    if row is None:
        return None
    return row[0], row[1], row[2]


def get_employment_history(
    db: Session, *, tenant_id: UUID, company_id: UUID, employee_id: UUID
) -> list[EmployeeEmployment]:
    stmt = (
        sa.select(EmployeeEmployment)
        .where(
            EmployeeEmployment.tenant_id == tenant_id,
            EmployeeEmployment.company_id == company_id,
            EmployeeEmployment.employee_id == employee_id,
        )
        .order_by(EmployeeEmployment.start_date.desc(), EmployeeEmployment.id.desc())
    )
    return list(db.execute(stmt).scalars().all())


def validate_branch_belongs_to_company(db: Session, *, company_id: UUID, branch_id: UUID) -> bool:
    return (
        db.execute(
            sa.text("SELECT 1 FROM tenancy.branches WHERE id = :branch_id AND company_id = :company_id"),
            {"company_id": company_id, "branch_id": branch_id},
        ).first()
        is not None
    )


def infer_company_id_from_branch(db: Session, *, branch_id: UUID) -> UUID | None:
    return db.execute(
        sa.text("SELECT company_id FROM tenancy.branches WHERE id = :branch_id"),
        {"branch_id": branch_id},
    ).scalar()


def get_user_by_id(db: Session, *, user_id: UUID) -> User | None:
    stmt = sa.select(User).where(User.id == user_id, User.deleted_at.is_(None))
    return db.execute(stmt).scalars().first()


def get_employee_by_id(db: Session, *, tenant_id: UUID, company_id: UUID, employee_id: UUID) -> Employee | None:
    stmt = sa.select(Employee).where(Employee.id == employee_id, Employee.tenant_id == tenant_id, Employee.company_id == company_id)
    return db.execute(stmt).scalars().first()


def get_person_by_id(db: Session, *, tenant_id: UUID, person_id: UUID) -> Person | None:
    stmt = sa.select(Person).where(Person.id == person_id, Person.tenant_id == tenant_id)
    return db.execute(stmt).scalars().first()


def get_employee_user_link(db: Session, *, employee_id: UUID) -> EmployeeUserLink | None:
    stmt = sa.select(EmployeeUserLink).where(EmployeeUserLink.employee_id == employee_id)
    return db.execute(stmt).scalars().first()


def insert_employee_user_link(db: Session, *, employee_id: UUID, user_id: UUID) -> EmployeeUserLink:
    link = EmployeeUserLink(employee_id=employee_id, user_id=user_id)
    db.add(link)
    return link


def validate_manager_constraints(
    db: Session,
    *,
    tenant_id: UUID,
    company_id: UUID,
    employee_id: UUID,
    manager_employee_id: UUID,
) -> None:
    if manager_employee_id == employee_id:
        raise AppError(code="hr.manager.cycle", message="Employee cannot be their own manager", status_code=400)

    # Manager must exist in the same tenant/company.
    exists = (
        db.execute(
            sa.text(
                """
                SELECT 1
                FROM hr_core.employees
                WHERE id = :manager_employee_id
                  AND tenant_id = :tenant_id
                  AND company_id = :company_id
                """
            ),
            {"manager_employee_id": manager_employee_id, "tenant_id": tenant_id, "company_id": company_id},
        ).first()
        is not None
    )
    if not exists:
        raise AppError(code="hr.manager.not_found", message="Manager not found in company scope", status_code=400)

    # Cycle detection over the current employment manager chain.
    cycle = (
        db.execute(
            sa.text(
                """
                WITH RECURSIVE chain AS (
                  SELECT ee.employee_id, ee.manager_employee_id, 1 AS depth
                  FROM hr_core.employee_employment ee
                  WHERE ee.tenant_id = :tenant_id
                    AND ee.company_id = :company_id
                    AND ee.employee_id = :start_employee_id
                    AND ee.end_date IS NULL

                  UNION ALL

                  SELECT ee.employee_id, ee.manager_employee_id, c.depth + 1 AS depth
                  FROM hr_core.employee_employment ee
                  JOIN chain c ON ee.employee_id = c.manager_employee_id
                  WHERE ee.tenant_id = :tenant_id
                    AND ee.company_id = :company_id
                    AND ee.end_date IS NULL
                    AND c.depth < 50
                )
                SELECT 1
                FROM chain
                WHERE employee_id = :target_employee_id
                LIMIT 1
                """
            ),
            {
                "tenant_id": tenant_id,
                "company_id": company_id,
                "start_employee_id": manager_employee_id,
                "target_employee_id": employee_id,
            },
        ).first()
        is not None
    )
    if cycle:
        raise AppError(code="hr.manager.cycle", message="Manager assignment creates a reporting cycle", status_code=400)
