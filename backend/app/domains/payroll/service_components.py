"""
Payroll component service (Milestone 9).

Components are a tenant-scoped catalog of earnings/deductions used by salary
structures and payrun computation.
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


class PayrollComponentService:
    """CRUD for `payroll.components` (tenant-scoped)."""

    def create_component(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        code: str,
        name: str,
        component_type: str,
        calc_mode: str,
        default_amount,
        default_percent,
        is_taxable: bool,
        is_active: bool,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id

        try:
            row = (
                db.execute(
                    sa.text(
                        """
                        INSERT INTO payroll.components (
                          tenant_id,
                          code,
                          name,
                          component_type,
                          calc_mode,
                          default_amount,
                          default_percent,
                          is_taxable,
                          is_active
                        ) VALUES (
                          :tenant_id,
                          :code,
                          :name,
                          :component_type,
                          :calc_mode,
                          :default_amount,
                          :default_percent,
                          :is_taxable,
                          :is_active
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "code": code,
                        "name": name,
                        "component_type": component_type,
                        "calc_mode": calc_mode,
                        "default_amount": default_amount,
                        "default_percent": default_percent,
                        "is_taxable": bool(is_taxable),
                        "is_active": bool(is_active),
                    },
                )
                .mappings()
                .first()
            )
            assert row is not None

            # Keep audit payload minimal (avoid logging amounts).
            audit_svc.record(
                db,
                ctx=ctx,
                action="payroll.component.create",
                entity_type="payroll.component",
                entity_id=UUID(str(row["id"])),
                before=None,
                after={
                    "code": str(code),
                    "name": str(name),
                    "component_type": str(component_type),
                    "calc_mode": str(calc_mode),
                    "is_active": bool(is_active),
                },
            )

            db.commit()
            return dict(row)
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="validation_error",
                message="Component code already exists",
                status_code=409,
            ) from e
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

    def list_components(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        component_type: str | None,
    ) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id

        where = ["tenant_id = :tenant_id"]
        params: dict[str, Any] = {"tenant_id": tenant_id}
        if component_type:
            where.append("component_type = :component_type")
            params["component_type"] = str(component_type)

        sql = f"""
            SELECT *
            FROM payroll.components
            WHERE {" AND ".join(where)}
            ORDER BY component_type ASC, code ASC, created_at ASC, id ASC
        """
        rows = db.execute(sa.text(sql), params).mappings().all()
        return [dict(r) for r in rows]

    def require_component(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        component_id: UUID,
    ) -> dict[str, Any]:
        row = (
            db.execute(
                sa.text(
                    """
                    SELECT *
                    FROM payroll.components
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                    """
                ),
                {"tenant_id": tenant_id, "id": component_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(
                code="payroll.component.not_found",
                message="Component not found",
                status_code=404,
            )
        return dict(row)

