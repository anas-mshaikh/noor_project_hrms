from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.hr_core import repo
from app.domains.hr_core.schemas import (
    Employee360Out,
    EmployeeCreateIn,
    EmployeeDirectoryRowOut,
    EmployeeLinkUserIn,
    EmployeePatchIn,
    EmployeeUserLinkOut,
    EssProfilePatchIn,
    EmploymentChangeIn,
    EmploymentOut,
    LinkedUserOut,
    ManagerSummaryOut,
    PersonOut,
    EmployeeOut,
)
from app.shared.types import AuthContext


@dataclass(frozen=True)
class _CompanyScope:
    tenant_id: UUID
    company_id: UUID


class HRCoreService:
    def _resolve_company_scope(self, *, ctx: AuthContext, company_id: UUID) -> _CompanyScope:
        if company_id not in ctx.scope.allowed_company_ids:
            raise AppError(code="forbidden", message="Company scope not allowed", status_code=403)

        # Non-tenant-level actors must operate within their active company.
        if "ADMIN" not in ctx.roles and ctx.scope.company_id is not None and company_id != ctx.scope.company_id:
            raise AppError(code="forbidden", message="Company scope not allowed", status_code=403)

        return _CompanyScope(tenant_id=ctx.scope.tenant_id, company_id=company_id)

    def _build_employee_360_out(self, row: repo.Employee360Row, *, view: str) -> Employee360Out:
        # HR and ESS currently share the same payload shape; the "view" flag exists
        # so we can restrict fields later without breaking API contracts.
        _ = view  # reserved

        current = row.current_employment
        mgr = row.manager
        linked = row.linked_user

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
            linked_user=(
                LinkedUserOut(
                    user_id=linked.user_id,
                    email=linked.email,
                    status=linked.status,
                    linked_at=linked.linked_at,
                )
                if linked is not None
                else None
            ),
        )

    # ------------------------------------------------------------------
    # HR endpoints
    # ------------------------------------------------------------------
    def create_employee(self, db: Session, *, ctx: AuthContext, payload: EmployeeCreateIn) -> Employee360Out:
        scope = self._resolve_company_scope(ctx=ctx, company_id=payload.employee.company_id)

        if not repo.validate_branch_belongs_to_company(db, company_id=scope.company_id, branch_id=payload.employment.branch_id):
            raise AppError(code="hr.branch.invalid", message="branch_id does not belong to company", status_code=400)

        if repo.employee_code_exists(db, company_id=scope.company_id, employee_code=payload.employee.employee_code):
            raise AppError(code="hr.employee.code_exists", message="employee_code already exists", status_code=409)

        employee_id: UUID | None = None
        try:
            person = repo.insert_person(
                db,
                tenant_id=scope.tenant_id,
                first_name=payload.person.first_name,
                last_name=payload.person.last_name,
                dob=payload.person.dob,
                nationality=payload.person.nationality,
                email=str(payload.person.email) if payload.person.email is not None else None,
                phone=payload.person.phone,
                address=payload.person.address,
            )
            employee = repo.insert_employee(
                db,
                tenant_id=scope.tenant_id,
                company_id=scope.company_id,
                person_id=person.id,
                employee_code=payload.employee.employee_code,
                status=payload.employee.status,
                join_date=payload.employee.join_date,
                termination_date=None,
            )
            employee_id = employee.id

            if payload.employment.manager_employee_id is not None:
                repo.validate_manager_constraints(
                    db,
                    tenant_id=scope.tenant_id,
                    company_id=scope.company_id,
                    employee_id=employee.id,
                    manager_employee_id=payload.employment.manager_employee_id,
                )

            repo.insert_employment(
                db,
                tenant_id=scope.tenant_id,
                company_id=scope.company_id,
                employee_id=employee.id,
                branch_id=payload.employment.branch_id,
                org_unit_id=payload.employment.org_unit_id,
                job_title_id=payload.employment.job_title_id,
                grade_id=payload.employment.grade_id,
                manager_employee_id=payload.employment.manager_employee_id,
                start_date=payload.employment.start_date,
                end_date=None,
                is_primary=bool(payload.employment.is_primary),
            )
            db.commit()
        except AppError:
            db.rollback()
            raise
        except IntegrityError as e:
            db.rollback()
            raise AppError(code="hr.employee.code_exists", message="employee_code already exists", status_code=409) from e
        except Exception:
            db.rollback()
            raise

        if employee_id is None:  # defensive
            raise AppError(code="internal_error", message="Employee create failed", status_code=500)

        row = repo.get_employee_360_by_id(
            db, tenant_id=scope.tenant_id, company_id=scope.company_id, employee_id=employee_id
        )
        if row is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found after create", status_code=500)
        return self._build_employee_360_out(row, view="hr")

    def list_employees(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        company_id: UUID,
        q: str | None,
        status: str | None,
        branch_id: UUID | None,
        org_unit_id: UUID | None,
        limit: int,
        offset: int,
    ) -> tuple[list[EmployeeDirectoryRowOut], int]:
        scope = self._resolve_company_scope(ctx=ctx, company_id=company_id)
        rows, total = repo.list_employees_directory(
            db,
            tenant_id=scope.tenant_id,
            company_id=scope.company_id,
            q=q,
            status=status,
            branch_id=branch_id,
            org_unit_id=org_unit_id,
            limit=limit,
            offset=offset,
        )
        items = [
            EmployeeDirectoryRowOut(
                employee_id=r.employee_id,
                employee_code=r.employee_code,
                status=r.status,  # type: ignore[arg-type]
                full_name=r.full_name,
                email=r.email,
                phone=r.phone,
                branch_id=r.branch_id,
                org_unit_id=r.org_unit_id,
                manager_employee_id=r.manager_employee_id,
                manager_name=r.manager_name,
                has_user_link=r.has_user_link,
            )
            for r in rows
        ]
        return items, total

    def get_employee(self, db: Session, *, ctx: AuthContext, company_id: UUID, employee_id: UUID) -> Employee360Out:
        scope = self._resolve_company_scope(ctx=ctx, company_id=company_id)
        row = repo.get_employee_360_by_id(db, tenant_id=scope.tenant_id, company_id=scope.company_id, employee_id=employee_id)
        if row is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)
        return self._build_employee_360_out(row, view="hr")

    def patch_employee(
        self, db: Session, *, ctx: AuthContext, company_id: UUID, employee_id: UUID, payload: EmployeePatchIn
    ) -> Employee360Out:
        scope = self._resolve_company_scope(ctx=ctx, company_id=company_id)
        row = repo.get_employee_360_by_id(db, tenant_id=scope.tenant_id, company_id=scope.company_id, employee_id=employee_id)
        if row is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)

        before = {
            "person": {
                "first_name": row.person.first_name,
                "last_name": row.person.last_name,
                "dob": str(row.person.dob) if row.person.dob is not None else None,
                "nationality": row.person.nationality,
                "email": row.person.email,
                "phone": row.person.phone,
                "address": row.person.address,
            },
            "employee": {
                "status": row.employee.status,
                "join_date": str(row.employee.join_date) if row.employee.join_date is not None else None,
                "termination_date": str(row.employee.termination_date) if row.employee.termination_date is not None else None,
            },
        }

        try:
            if payload.person is not None:
                p = row.person
                if payload.person.first_name is not None:
                    p.first_name = payload.person.first_name
                if payload.person.last_name is not None:
                    p.last_name = payload.person.last_name
                if payload.person.dob is not None:
                    p.dob = payload.person.dob
                if payload.person.nationality is not None:
                    p.nationality = payload.person.nationality
                if payload.person.email is not None:
                    p.email = str(payload.person.email)
                if payload.person.phone is not None:
                    p.phone = payload.person.phone
                if payload.person.address is not None:
                    p.address = payload.person.address

            if payload.employee is not None:
                e = row.employee
                new_status = payload.employee.status or e.status
                new_termination_date = (
                    payload.employee.termination_date if payload.employee.termination_date is not None else e.termination_date
                )

                if new_status == "TERMINATED" and new_termination_date is None:
                    raise AppError(
                        code="hr.employee.invalid_patch",
                        message="termination_date is required when status is TERMINATED",
                        status_code=400,
                    )

                if payload.employee.status is not None:
                    e.status = payload.employee.status
                if payload.employee.join_date is not None:
                    e.join_date = payload.employee.join_date
                if payload.employee.termination_date is not None:
                    e.termination_date = payload.employee.termination_date

            after = {
                "person": {
                    "first_name": row.person.first_name,
                    "last_name": row.person.last_name,
                    "dob": str(row.person.dob) if row.person.dob is not None else None,
                    "nationality": row.person.nationality,
                    "email": row.person.email,
                    "phone": row.person.phone,
                    "address": row.person.address,
                },
                "employee": {
                    "status": row.employee.status,
                    "join_date": str(row.employee.join_date) if row.employee.join_date is not None else None,
                    "termination_date": str(row.employee.termination_date) if row.employee.termination_date is not None else None,
                },
            }
            audit_svc.record(
                db,
                ctx=ctx,
                action="hr.employee.patch",
                entity_type="hr_core.employee",
                entity_id=row.employee.id,
                before=before,
                after=after,
            )

            db.commit()
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise
        refreshed = repo.get_employee_360_by_id(
            db, tenant_id=scope.tenant_id, company_id=scope.company_id, employee_id=employee_id
        )
        if refreshed is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)
        return self._build_employee_360_out(refreshed, view="hr")

    def change_employment(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        company_id: UUID,
        employee_id: UUID,
        payload: EmploymentChangeIn,
    ) -> Employee360Out:
        scope = self._resolve_company_scope(ctx=ctx, company_id=company_id)

        current = repo.get_current_employment(db, tenant_id=scope.tenant_id, company_id=scope.company_id, employee_id=employee_id)
        if current is None:
            raise AppError(code="hr.employee.invalid_employment", message="Employee has no current employment", status_code=400)

        if payload.start_date <= current.start_date:
            raise AppError(code="hr.employee.invalid_employment", message="start_date must be after current start_date", status_code=400)

        if not repo.validate_branch_belongs_to_company(db, company_id=scope.company_id, branch_id=payload.branch_id):
            raise AppError(code="hr.branch.invalid", message="branch_id does not belong to company", status_code=400)

        if payload.manager_employee_id is not None:
            repo.validate_manager_constraints(
                db,
                tenant_id=scope.tenant_id,
                company_id=scope.company_id,
                employee_id=employee_id,
                manager_employee_id=payload.manager_employee_id,
            )

        before_emp = {
            "employee_id": str(employee_id),
            "previous_employment_id": str(current.id),
            "previous_branch_id": str(current.branch_id),
            "previous_start_date": str(current.start_date),
            "previous_end_date": str(current.end_date) if current.end_date is not None else None,
            "previous_manager_employee_id": str(current.manager_employee_id)
            if current.manager_employee_id is not None
            else None,
        }

        # Close current employment using a same-day boundary:
        # old.end_date = new.start_date, new.start_date = requested start_date.
        # This avoids date arithmetic and keeps the history deterministic.
        current.end_date = payload.start_date

        new_emp = repo.insert_employment(
            db,
            tenant_id=scope.tenant_id,
            company_id=scope.company_id,
            employee_id=employee_id,
            branch_id=payload.branch_id,
            org_unit_id=payload.org_unit_id,
            job_title_id=payload.job_title_id,
            grade_id=payload.grade_id,
            manager_employee_id=payload.manager_employee_id,
            start_date=payload.start_date,
            end_date=None,
            is_primary=True,
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="hr.employee.change_employment",
            entity_type="hr_core.employee_employment",
            entity_id=new_emp.id,
            before=before_emp,
            after={
                "employee_id": str(employee_id),
                "new_employment_id": str(new_emp.id),
                "new_branch_id": str(new_emp.branch_id),
                "new_start_date": str(new_emp.start_date),
                "new_manager_employee_id": str(new_emp.manager_employee_id)
                if new_emp.manager_employee_id is not None
                else None,
            },
        )
        try:
            db.commit()
        except Exception:
            db.rollback()
            raise
        refreshed = repo.get_employee_360_by_id(
            db, tenant_id=scope.tenant_id, company_id=scope.company_id, employee_id=employee_id
        )
        if refreshed is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)
        return self._build_employee_360_out(refreshed, view="hr")

    def list_employment_history(self, db: Session, *, ctx: AuthContext, company_id: UUID, employee_id: UUID) -> list[EmploymentOut]:
        scope = self._resolve_company_scope(ctx=ctx, company_id=company_id)
        if repo.get_employee_by_id(db, tenant_id=scope.tenant_id, company_id=scope.company_id, employee_id=employee_id) is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)
        rows = repo.get_employment_history(db, tenant_id=scope.tenant_id, company_id=scope.company_id, employee_id=employee_id)
        return [
            EmploymentOut(
                id=r.id,
                tenant_id=r.tenant_id,
                company_id=r.company_id,
                employee_id=r.employee_id,
                branch_id=r.branch_id,
                org_unit_id=r.org_unit_id,
                job_title_id=r.job_title_id,
                grade_id=r.grade_id,
                manager_employee_id=r.manager_employee_id,
                start_date=r.start_date,
                end_date=r.end_date,
                is_primary=r.is_primary,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    def link_user(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        company_id: UUID,
        employee_id: UUID,
        payload: EmployeeLinkUserIn,
    ) -> EmployeeUserLinkOut:
        scope = self._resolve_company_scope(ctx=ctx, company_id=company_id)
        if repo.get_employee_by_id(db, tenant_id=scope.tenant_id, company_id=scope.company_id, employee_id=employee_id) is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)

        existing = repo.get_employee_user_link(db, employee_id=employee_id)
        if existing is not None:
            # Idempotent: linking the same user twice is safe.
            if existing.user_id == payload.user_id:
                return EmployeeUserLinkOut(
                    employee_id=existing.employee_id,
                    user_id=existing.user_id,
                    created_at=existing.created_at,
                )

            raise AppError(
                code="hr.employee_user_link.conflict",
                message="Employee is already linked to a different user",
                status_code=409,
                details={
                    "employee_id": str(employee_id),
                    "existing_user_id": str(existing.user_id),
                    "requested_user_id": str(payload.user_id),
                },
            )

        user = repo.get_user_by_id(db, user_id=payload.user_id)
        if user is None:
            raise AppError(code="iam.user.not_found", message="User not found", status_code=404)

        mapping = repo.get_employee_id_by_user_id(db, user_id=payload.user_id)
        if mapping is not None and mapping[0] != employee_id:
            linked_employee_id, linked_tenant_id, _linked_company_id = mapping
            details = {
                "user_id": str(payload.user_id),
                "employee_id": str(employee_id),
            }
            # Avoid cross-tenant leakage: only include the linked employee id when
            # it belongs to the current tenant.
            if linked_tenant_id == scope.tenant_id:
                details["linked_employee_id"] = str(linked_employee_id)
            raise AppError(
                code="hr.employee_user_link.user_in_use",
                message="User is already linked to a different employee",
                status_code=409,
                details=details,
            )

        try:
            link = repo.insert_employee_user_link(db, employee_id=employee_id, user_id=payload.user_id)

            audit_svc.record(
                db,
                ctx=ctx,
                action="hr.employee.link_user",
                entity_type="hr_core.employee_user_link",
                entity_id=employee_id,
                before=None,
                after={
                    "employee_id": str(employee_id),
                    "user_id": str(payload.user_id),
                },
            )

            db.execute(
                sa.text(
                    """
                    INSERT INTO workflow.notification_outbox (
                      tenant_id, channel, recipient_user_id, template_code, payload
                    ) VALUES (
                      :tenant_id, 'IN_APP', :recipient_user_id, :template_code, CAST(:payload AS jsonb)
                    )
                    """
                ),
                {
                    "tenant_id": scope.tenant_id,
                    "recipient_user_id": payload.user_id,
                    "template_code": "EMPLOYEE_LINKED",
                    "payload": json.dumps(
                        {
                            "title": "Employee linked",
                            "body": "Your user account was linked to an employee profile.",
                            "employee_id": str(employee_id),
                            "company_id": str(scope.company_id),
                            "correlation_id": ctx.correlation_id,
                        },
                        default=str,
                    ),
                },
            )
            db.commit()
        except IntegrityError as e:
            db.rollback()
            # Best-effort conflict disambiguation (race-safe).
            refreshed = repo.get_employee_user_link(db, employee_id=employee_id)
            if refreshed is not None:
                if refreshed.user_id == payload.user_id:
                    return EmployeeUserLinkOut(
                        employee_id=refreshed.employee_id,
                        user_id=refreshed.user_id,
                        created_at=refreshed.created_at,
                    )
                raise AppError(
                    code="hr.employee_user_link.conflict",
                    message="Employee is already linked to a different user",
                    status_code=409,
                    details={
                        "employee_id": str(employee_id),
                        "existing_user_id": str(refreshed.user_id),
                        "requested_user_id": str(payload.user_id),
                    },
                ) from e

            refreshed_mapping = repo.get_employee_id_by_user_id(db, user_id=payload.user_id)
            if refreshed_mapping is not None and refreshed_mapping[0] != employee_id:
                linked_employee_id, linked_tenant_id, _linked_company_id = refreshed_mapping
                details = {
                    "user_id": str(payload.user_id),
                    "employee_id": str(employee_id),
                }
                if linked_tenant_id == scope.tenant_id:
                    details["linked_employee_id"] = str(linked_employee_id)
                raise AppError(
                    code="hr.employee_user_link.user_in_use",
                    message="User is already linked to a different employee",
                    status_code=409,
                    details=details,
                ) from e

            raise AppError(
                code="hr.employee_user_link.duplicate",
                message="Employee/user link already exists",
                status_code=409,
            ) from e

        return EmployeeUserLinkOut(employee_id=link.employee_id, user_id=link.user_id, created_at=link.created_at)

    # ------------------------------------------------------------------
    # ESS endpoints
    # ------------------------------------------------------------------
    def ess_get_profile(self, db: Session, *, ctx: AuthContext) -> Employee360Out:
        mapping = repo.get_employee_id_by_user_id(db, user_id=ctx.user_id)
        if mapping is None:
            raise AppError(code="ess.not_linked", message="User is not linked to an employee", status_code=409)
        employee_id, tenant_id, company_id = mapping

        if tenant_id not in ctx.scope.allowed_tenant_ids:
            raise AppError(code="forbidden", message="Tenant scope not allowed", status_code=403)

        row = repo.get_employee_360_by_id(db, tenant_id=tenant_id, company_id=company_id, employee_id=employee_id)
        if row is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)
        return self._build_employee_360_out(row, view="ess")

    def ess_patch_profile(self, db: Session, *, ctx: AuthContext, payload: EssProfilePatchIn) -> Employee360Out:
        extras = getattr(payload, "model_extra", None) or getattr(payload, "__pydantic_extra__", None)
        if extras:
            raise AppError(
                code="ess.profile.invalid_field",
                message="Only email, phone, and address can be updated",
                status_code=400,
                details={"fields": sorted(list(extras.keys()))},
            )

        mapping = repo.get_employee_id_by_user_id(db, user_id=ctx.user_id)
        if mapping is None:
            raise AppError(code="ess.not_linked", message="User is not linked to an employee", status_code=409)
        employee_id, tenant_id, company_id = mapping

        row = repo.get_employee_360_by_id(db, tenant_id=tenant_id, company_id=company_id, employee_id=employee_id)
        if row is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)

        p = row.person
        if payload.email is not None:
            p.email = str(payload.email)
        if payload.phone is not None:
            p.phone = payload.phone
        if payload.address is not None:
            p.address = payload.address

        try:
            db.commit()
        except Exception:
            db.rollback()
            raise

        refreshed = repo.get_employee_360_by_id(db, tenant_id=tenant_id, company_id=company_id, employee_id=employee_id)
        if refreshed is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)
        return self._build_employee_360_out(refreshed, view="ess")
