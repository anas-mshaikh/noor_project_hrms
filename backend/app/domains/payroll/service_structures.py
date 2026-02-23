"""
Salary structure services (Milestone 9).

Structures define an ordered list of payroll components (earnings/deductions)
that the payrun engine evaluates deterministically.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.payroll.service_components import PayrollComponentService
from app.shared.types import AuthContext


class SalaryStructureService:
    """CRUD for `payroll.salary_structures` and `payroll.salary_structure_lines`."""

    def __init__(self) -> None:
        self._components = PayrollComponentService()

    def create_structure(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        code: str,
        name: str,
        is_active: bool,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id

        try:
            row = (
                db.execute(
                    sa.text(
                        """
                        INSERT INTO payroll.salary_structures (
                          tenant_id,
                          code,
                          name,
                          is_active
                        ) VALUES (
                          :tenant_id,
                          :code,
                          :name,
                          :is_active
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "code": code,
                        "name": name,
                        "is_active": bool(is_active),
                    },
                )
                .mappings()
                .first()
            )
            assert row is not None

            audit_svc.record(
                db,
                ctx=ctx,
                action="payroll.structure.create",
                entity_type="payroll.salary_structure",
                entity_id=UUID(str(row["id"])),
                before=None,
                after={"code": str(code), "name": str(name), "is_active": bool(is_active)},
            )

            db.commit()
            return dict(row)
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="validation_error",
                message="Salary structure code already exists",
                status_code=409,
            ) from e
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

    def add_line(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        structure_id: UUID,
        component_id: UUID,
        sort_order: int,
        calc_mode_override: str | None,
        amount_override,
        percent_override,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id

        st = self._get_structure_row(db, tenant_id=tenant_id, structure_id=structure_id)
        if st is None:
            raise AppError(code="payroll.structure.not_found", message="Salary structure not found", status_code=404)

        # Component must exist within the tenant.
        self._components.require_component(db, tenant_id=tenant_id, component_id=component_id)

        # Keep v1 deterministic by requiring sort_order uniqueness per structure.
        dup = db.execute(
            sa.text(
                """
                SELECT 1
                FROM payroll.salary_structure_lines
                WHERE tenant_id = :tenant_id
                  AND salary_structure_id = :structure_id
                  AND sort_order = :sort_order
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id, "structure_id": structure_id, "sort_order": int(sort_order)},
        ).first()
        if dup is not None:
            raise AppError(
                code="validation_error",
                message="sort_order must be unique within a salary structure",
                status_code=409,
            )

        try:
            row = (
                db.execute(
                    sa.text(
                        """
                        INSERT INTO payroll.salary_structure_lines (
                          tenant_id,
                          salary_structure_id,
                          component_id,
                          sort_order,
                          calc_mode_override,
                          amount_override,
                          percent_override
                        ) VALUES (
                          :tenant_id,
                          :structure_id,
                          :component_id,
                          :sort_order,
                          :calc_mode_override,
                          :amount_override,
                          :percent_override
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "structure_id": structure_id,
                        "component_id": component_id,
                        "sort_order": int(sort_order),
                        "calc_mode_override": calc_mode_override,
                        "amount_override": amount_override,
                        "percent_override": percent_override,
                    },
                )
                .mappings()
                .first()
            )
            assert row is not None

            audit_svc.record(
                db,
                ctx=ctx,
                action="payroll.structure.line.create",
                entity_type="payroll.salary_structure_line",
                entity_id=UUID(str(row["id"])),
                before=None,
                after={
                    "salary_structure_id": str(structure_id),
                    "component_id": str(component_id),
                    "sort_order": int(sort_order),
                },
            )

            db.commit()
            return dict(row)
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="validation_error",
                message="Component already exists on structure",
                status_code=409,
            ) from e
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

    def get_structure_detail(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        structure_id: UUID,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        tenant_id = ctx.scope.tenant_id

        st = self._get_structure_row(db, tenant_id=tenant_id, structure_id=structure_id)
        if st is None:
            raise AppError(code="payroll.structure.not_found", message="Salary structure not found", status_code=404)

        lines = (
            db.execute(
                sa.text(
                    """
                    SELECT *
                    FROM payroll.salary_structure_lines
                    WHERE tenant_id = :tenant_id
                      AND salary_structure_id = :structure_id
                    ORDER BY sort_order ASC, created_at ASC, id ASC
                    """
                ),
                {"tenant_id": tenant_id, "structure_id": structure_id},
            )
            .mappings()
            .all()
        )
        return dict(st), [dict(r) for r in lines]

    def _get_structure_row(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        structure_id: UUID,
    ) -> dict[str, Any] | None:
        row = (
            db.execute(
                sa.text(
                    """
                    SELECT *
                    FROM payroll.salary_structures
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                    """
                ),
                {"tenant_id": tenant_id, "id": structure_id},
            )
            .mappings()
            .first()
        )
        return dict(row) if row is not None else None

