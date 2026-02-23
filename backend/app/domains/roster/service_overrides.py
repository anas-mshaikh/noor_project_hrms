"""
Roster override service (Milestone 8).

Roster overrides provide per-employee per-day control:
- SHIFT_CHANGE: use a different shift template for that day
- WEEKOFF: force day_type=WEEKOFF regardless of branch calendar
- WORKDAY: force day_type=WORKDAY regardless of branch calendar

The override table is unique per (tenant, employee, day) and implemented as an
UPSERT for deterministic behavior.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.shared.types import AuthContext


class RosterOverrideService:
    """Upsert/list roster overrides."""

    def _resolve_employee_current_branch(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        employee_id: UUID,
    ) -> tuple[UUID, UUID]:
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
        # Same hardening rationale as ShiftAssignmentService.
        if ctx.scope.company_id is not None and ctx.scope.company_id != employee_company_id:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)
        if ctx.scope.branch_id is not None and ctx.scope.branch_id != employee_branch_id:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)

    def upsert_override(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        employee_id: UUID,
        day,
        override_type: str,
        shift_template_id: UUID | None,
        notes: str | None,
    ) -> dict[str, Any]:
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

        # Domain validation for override shape.
        if override_type == "WEEKOFF" and shift_template_id is not None:
            raise AppError(
                code="roster.override.invalid",
                message="WEEKOFF override must not specify shift_template_id",
                status_code=400,
            )
        if override_type == "SHIFT_CHANGE" and shift_template_id is None:
            raise AppError(
                code="roster.override.invalid",
                message="SHIFT_CHANGE override requires shift_template_id",
                status_code=400,
            )

        if shift_template_id is not None:
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
                {
                    "tenant_id": tenant_id,
                    "branch_id": employee_branch_id,
                    "id": shift_template_id,
                },
            ).first()
            if st is None:
                raise AppError(
                    code="roster.shift.not_found",
                    message="Shift template not found for employee branch",
                    status_code=404,
                )

        try:
            row = (
                db.execute(
                    sa.text(
                        """
                        INSERT INTO roster.roster_overrides (
                          tenant_id,
                          employee_id,
                          branch_id,
                          day,
                          override_type,
                          shift_template_id,
                          notes,
                          created_by_user_id
                        ) VALUES (
                          :tenant_id,
                          :employee_id,
                          :branch_id,
                          :day,
                          :override_type,
                          :shift_template_id,
                          :notes,
                          :created_by_user_id
                        )
                        ON CONFLICT (tenant_id, employee_id, day)
                        DO UPDATE SET
                          override_type = EXCLUDED.override_type,
                          shift_template_id = EXCLUDED.shift_template_id,
                          notes = EXCLUDED.notes
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "employee_id": employee_id,
                        "branch_id": employee_branch_id,
                        "day": day,
                        "override_type": override_type,
                        "shift_template_id": shift_template_id,
                        "notes": notes,
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
                action="roster.override.upsert",
                entity_type="roster.roster_override",
                entity_id=UUID(str(row["id"])),
                before=None,
                after={
                    "employee_id": str(employee_id),
                    "branch_id": str(employee_branch_id),
                    "day": str(day),
                    "override_type": str(override_type),
                    "shift_template_id": str(shift_template_id) if shift_template_id is not None else None,
                },
            )

            db.commit()
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

        return dict(row)

    def list_overrides(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        employee_id: UUID,
        from_day,
        to_day,
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
                FROM roster.roster_overrides
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND day >= :from_day
                  AND day <= :to_day
                ORDER BY day ASC, created_at ASC, id ASC
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id, "from_day": from_day, "to_day": to_day},
        ).mappings().all()
        return [dict(r) for r in rows]

