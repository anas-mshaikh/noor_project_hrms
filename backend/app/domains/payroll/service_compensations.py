"""
Employee compensation service (Milestone 9).

Compensation is effective-dated and references a salary structure.
In v1, base_amount is a monthly base that is prorated by payable_days.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.payroll.utils import json_canonical
from app.shared.types import AuthContext


class EmployeeCompensationService:
    """Create/list `payroll.employee_compensations` (effective-dated)."""

    def _resolve_employee_current_scope(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        employee_id: UUID,
    ) -> tuple[UUID, UUID]:
        """
        Resolve (company_id, branch_id) from the canonical current-employment view.

        We use this for scope hardening on employee-scoped endpoints.
        """

        row = (
            db.execute(
                sa.text(
                    """
                    SELECT company_id, branch_id
                    FROM hr_core.v_employee_current_employment
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                    """
                ),
                {"tenant_id": tenant_id, "employee_id": employee_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)
        return UUID(str(row["company_id"])), UUID(str(row["branch_id"]))

    def _enforce_scope_allows_employee(
        self,
        *,
        ctx: AuthContext,
        employee_company_id: UUID,
        employee_branch_id: UUID,
    ) -> None:
        """
        Harden branch-scoped HR tokens.

        Without this check, a branch-scoped actor could operate on other
        branches by guessing employee UUIDs.
        """

        if ctx.scope.company_id is not None and ctx.scope.company_id != employee_company_id:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)
        if ctx.scope.branch_id is not None and ctx.scope.branch_id != employee_branch_id:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)

    def upsert_compensation(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        employee_id: UUID,
        currency_code: str,
        salary_structure_id: UUID,
        base_amount,
        effective_from,
        effective_to,
        overrides_json: dict[str, Any] | None,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id

        if effective_to is not None and effective_to < effective_from:
            raise AppError(code="validation_error", message="effective_to must be >= effective_from", status_code=400)

        employee_company_id, employee_branch_id = self._resolve_employee_current_scope(
            db, tenant_id=tenant_id, employee_id=employee_id
        )
        self._enforce_scope_allows_employee(
            ctx=ctx,
            employee_company_id=employee_company_id,
            employee_branch_id=employee_branch_id,
        )

        st = db.execute(
            sa.text(
                """
                SELECT 1
                FROM payroll.salary_structures
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": salary_structure_id},
        ).first()
        if st is None:
            raise AppError(code="payroll.structure.not_found", message="Salary structure not found", status_code=404)

        # Overlap validation (deterministic):
        overlap = db.execute(
            sa.text(
                """
                SELECT 1
                FROM payroll.employee_compensations
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND NOT (
                    COALESCE(effective_to, '9999-12-31'::date) < :new_from
                    OR COALESCE(CAST(:new_to AS date), '9999-12-31'::date) < effective_from
                  )
                LIMIT 1
                """
            ),
            {
                "tenant_id": tenant_id,
                "employee_id": employee_id,
                "new_from": effective_from,
                "new_to": effective_to,
            },
        ).first()
        if overlap is not None:
            raise AppError(
                code="payroll.compensation.overlap",
                message="Compensation overlaps an existing record",
                status_code=409,
            )

        try:
            row = (
                db.execute(
                    sa.text(
                        """
                        INSERT INTO payroll.employee_compensations (
                          tenant_id,
                          employee_id,
                          currency_code,
                          salary_structure_id,
                          base_amount,
                          effective_from,
                          effective_to,
                          overrides_json,
                          created_by_user_id
                        ) VALUES (
                          :tenant_id,
                          :employee_id,
                          :currency_code,
                          :salary_structure_id,
                          :base_amount,
                          :effective_from,
                          :effective_to,
                          CAST(:overrides_json AS jsonb),
                          :created_by_user_id
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "employee_id": employee_id,
                        "currency_code": currency_code,
                        "salary_structure_id": salary_structure_id,
                        "base_amount": base_amount,
                        "effective_from": effective_from,
                        "effective_to": effective_to,
                        "overrides_json": json_canonical(overrides_json or {}),
                        "created_by_user_id": ctx.user_id,
                    },
                )
                .mappings()
                .first()
            )
            assert row is not None

            # Avoid logging base_amount in audits; store only effective-dating metadata.
            audit_svc.record(
                db,
                ctx=ctx,
                action="payroll.compensation.upsert",
                entity_type="payroll.employee_compensation",
                entity_id=UUID(str(row["id"])),
                before=None,
                after={
                    "employee_id": str(employee_id),
                    "salary_structure_id": str(salary_structure_id),
                    "currency_code": str(currency_code),
                    "effective_from": str(effective_from),
                    "effective_to": str(effective_to) if effective_to is not None else None,
                },
            )

            db.commit()
            return dict(row)
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="payroll.compensation.overlap",
                message="Compensation overlaps an existing record",
                status_code=409,
            ) from e
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

    def list_compensations(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        employee_id: UUID,
    ) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id

        employee_company_id, employee_branch_id = self._resolve_employee_current_scope(
            db, tenant_id=tenant_id, employee_id=employee_id
        )
        self._enforce_scope_allows_employee(
            ctx=ctx,
            employee_company_id=employee_company_id,
            employee_branch_id=employee_branch_id,
        )

        rows = (
            db.execute(
                sa.text(
                    """
                    SELECT *
                    FROM payroll.employee_compensations
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                    ORDER BY effective_from DESC, created_at DESC, id DESC
                    """
                ),
                {"tenant_id": tenant_id, "employee_id": employee_id},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]
