"""
Shift assignment service (Milestone 8).

Responsibilities:
- Persist effective-dated shift assignments per employee.
- Enforce deterministic "no overlap" invariants for v1.
- Snapshot employee branch_id at assignment time for reporting.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.shared.types import AuthContext


class ShiftAssignmentService:
    """Create/list employee shift assignments (effective dated)."""

    # ------------------------------------------------------------------
    # Employee resolution helpers
    # ------------------------------------------------------------------
    def _resolve_employee_current_branch(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        employee_id: UUID,
    ) -> tuple[UUID, UUID]:
        """
        Resolve (company_id, branch_id) for the employee's current employment.

        We use `hr_core.v_employee_current_employment` so selection stays consistent
        with other domains (attendance punching, profile-change filters, etc.).
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
            raise AppError(
                code="hr.employee.not_found",
                message="Employee not found",
                status_code=404,
            )

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

        Rationale:
        - Endpoints like `/roster/employees/{employee_id}/...` do not include branch_id
          in the path, so scope headers remain whatever the caller selected.
        - Without this check, a branch-scoped HR actor could operate on other branches
          by guessing employee UUIDs.
        """

        if ctx.scope.company_id is not None and ctx.scope.company_id != employee_company_id:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)
        if ctx.scope.branch_id is not None and ctx.scope.branch_id != employee_branch_id:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    def create_assignment(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        employee_id: UUID,
        shift_template_id: UUID,
        effective_from,
        effective_to,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id

        if effective_to is not None and effective_to < effective_from:
            raise AppError(
                code="roster.assignment.invalid_dates",
                message="effective_to must be >= effective_from",
                status_code=400,
            )

        employee_company_id, employee_branch_id = self._resolve_employee_current_branch(
            db,
            tenant_id=tenant_id,
            employee_id=employee_id,
        )
        self._enforce_scope_allows_employee(
            ctx=ctx,
            employee_company_id=employee_company_id,
            employee_branch_id=employee_branch_id,
        )

        # Shift template must belong to the employee's current branch.
        st = db.execute(
            sa.text(
                """
                SELECT 1
                FROM roster.shift_templates
                WHERE tenant_id = :tenant_id
                  AND branch_id = :branch_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "branch_id": employee_branch_id, "id": shift_template_id},
        ).first()
        if st is None:
            raise AppError(
                code="roster.shift.not_found",
                message="Shift template not found for employee branch",
                status_code=404,
            )

        # Overlap validation (deterministic):
        # Two date ranges overlap unless one ends strictly before the other starts.
        overlap = db.execute(
            sa.text(
                """
                SELECT 1
                FROM roster.shift_assignments
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
                code="roster.assignment.overlap",
                message="Shift assignment overlaps an existing assignment",
                status_code=409,
            )

        try:
            row = (
                db.execute(
                    sa.text(
                        """
                        INSERT INTO roster.shift_assignments (
                          tenant_id,
                          employee_id,
                          branch_id,
                          shift_template_id,
                          effective_from,
                          effective_to,
                          created_by_user_id
                        ) VALUES (
                          :tenant_id,
                          :employee_id,
                          :branch_id,
                          :shift_template_id,
                          :effective_from,
                          :effective_to,
                          :created_by_user_id
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "employee_id": employee_id,
                        "branch_id": employee_branch_id,
                        "shift_template_id": shift_template_id,
                        "effective_from": effective_from,
                        "effective_to": effective_to,
                        "created_by_user_id": ctx.user_id,
                    },
                )
                .mappings()
                .first()
            )
            assert row is not None

            audit_svc.record(
                db,
                ctx=ctx,
                action="roster.assignment.create",
                entity_type="roster.shift_assignment",
                entity_id=UUID(str(row["id"])),
                before=None,
                after={
                    "employee_id": str(employee_id),
                    "branch_id": str(employee_branch_id),
                    "shift_template_id": str(shift_template_id),
                    "effective_from": str(effective_from),
                    "effective_to": str(effective_to) if effective_to is not None else None,
                },
            )

            db.commit()
        except IntegrityError as e:
            db.rollback()
            # Most common: active assignment unique index.
            raise AppError(
                code="roster.assignment.overlap",
                message="Shift assignment overlaps an existing assignment",
                status_code=409,
            ) from e
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

        return dict(row)

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------
    def list_assignments(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        employee_id: UUID,
    ) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id

        employee_company_id, employee_branch_id = self._resolve_employee_current_branch(
            db,
            tenant_id=tenant_id,
            employee_id=employee_id,
        )
        self._enforce_scope_allows_employee(
            ctx=ctx,
            employee_company_id=employee_company_id,
            employee_branch_id=employee_branch_id,
        )

        rows = db.execute(
            sa.text(
                """
                SELECT *
                FROM roster.shift_assignments
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                ORDER BY effective_from DESC, created_at DESC, id DESC
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id},
        ).mappings().all()
        return [dict(r) for r in rows]

