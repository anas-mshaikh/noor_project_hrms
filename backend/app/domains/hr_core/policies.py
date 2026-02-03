from __future__ import annotations

from fastapi import Depends

from app.auth.deps import get_auth_context, require_roles
from app.domains.hr_core import repo as hr_repo
from app.domains.hr_core.schemas import (
    Employee360Out,
    EmployeeOut,
    EmploymentOut,
    ManagerSummaryOut,
    MSSEmployeeOut,
    MSSEmployeeProfileOut,
    MSSEmploymentOut,
    MSSPersonOut,
    PersonOut,
)
from app.shared.types import AuthContext


def require_hr_read(ctx: AuthContext = Depends(require_roles(["ADMIN", "HR_ADMIN", "HR_MANAGER"]))) -> AuthContext:
    return ctx


def require_hr_write(ctx: AuthContext = Depends(require_roles(["ADMIN", "HR_ADMIN"]))) -> AuthContext:
    return ctx


def require_ess_user(ctx: AuthContext = Depends(get_auth_context)) -> AuthContext:
    # ESS endpoints are for any authenticated user; role-based restrictions
    # are enforced by employee linkage and record-level rules.
    return ctx


def require_mss_access(ctx: AuthContext = Depends(require_roles(["ADMIN", "HR_ADMIN", "HR_MANAGER", "MANAGER"]))) -> AuthContext:
    return ctx


def is_self(*, employee_id: str, actor_employee_id: str) -> bool:
    return employee_id == actor_employee_id


def project_employee_360_hr(row: hr_repo.Employee360Row) -> Employee360Out:
    current = row.current_employment
    mgr = row.manager

    return Employee360Out(
        employee=EmployeeOut(
            id=row.employee.id,
            tenant_id=row.employee.tenant_id,
            company_id=row.employee.company_id,
            person_id=row.employee.person_id,
            employee_code=row.employee.employee_code,
            status=row.employee.status,
            join_date=row.employee.join_date,
            termination_date=row.employee.termination_date,
            created_at=row.employee.created_at,
            updated_at=row.employee.updated_at,
        ),
        person=PersonOut(
            id=row.person.id,
            tenant_id=row.person.tenant_id,
            first_name=row.person.first_name,
            last_name=row.person.last_name,
            dob=row.person.dob,
            nationality=row.person.nationality,
            email=row.person.email,
            phone=row.person.phone,
            address=row.person.address,
            created_at=row.person.created_at,
            updated_at=row.person.updated_at,
        ),
        current_employment=(
            EmploymentOut(
                id=current.id,
                tenant_id=current.tenant_id,
                company_id=current.company_id,
                employee_id=current.employee_id,
                branch_id=current.branch_id,
                org_unit_id=current.org_unit_id,
                job_title_id=current.job_title_id,
                grade_id=current.grade_id,
                manager_employee_id=current.manager_employee_id,
                start_date=current.start_date,
                end_date=current.end_date,
                is_primary=current.is_primary,
                created_at=current.created_at,
                updated_at=current.updated_at,
            )
            if current is not None
            else None
        ),
        manager=(
            ManagerSummaryOut(
                employee_id=mgr.employee_id,
                display_name=mgr.display_name,
                employee_code=mgr.employee_code,
            )
            if mgr is not None
            else None
        ),
    )


def project_employee_360_ess(row: hr_repo.Employee360Row) -> Employee360Out:
    # ESS currently shares the same shape as HR; field-level write restrictions
    # are enforced via the ESS patch schema and service.
    return project_employee_360_hr(row)


def project_employee_360_mss(row: hr_repo.Employee360Row) -> MSSEmployeeProfileOut:
    current = row.current_employment
    mgr = row.manager

    # MSS is explicitly restricted: no DOB, nationality, or address.
    person = MSSPersonOut(
        first_name=row.person.first_name,
        last_name=row.person.last_name,
        email=row.person.email,
        phone=row.person.phone,
    )
    employee = MSSEmployeeOut(
        id=row.employee.id,
        employee_code=row.employee.employee_code,
        status=row.employee.status,
        join_date=row.employee.join_date,
        termination_date=row.employee.termination_date,
    )

    return MSSEmployeeProfileOut(
        employee=employee,
        person=person,
        current_employment=(
            MSSEmploymentOut(
                branch_id=current.branch_id,
                org_unit_id=current.org_unit_id,
                job_title_id=current.job_title_id,
                grade_id=current.grade_id,
                manager_employee_id=current.manager_employee_id,
            )
            if current is not None
            else None
        ),
        manager=(
            ManagerSummaryOut(
                employee_id=mgr.employee_id,
                display_name=mgr.display_name,
                employee_code=mgr.employee_code,
            )
            if mgr is not None
            else None
        ),
    )
