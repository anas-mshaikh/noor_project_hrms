"""
Branch default shift service (Milestone 8).

This service manages `roster.branch_defaults`, which defines a fallback shift
template for a branch when an employee has no effective-dated assignment and no
per-day override specifies a shift.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.shared.types import AuthContext


class BranchDefaultShiftService:
    """Read/write branch default shift settings."""

    def set_default_shift(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        branch_id: UUID,
        shift_template_id: UUID,
    ) -> dict[str, Any]:
        """
        Upsert the branch default shift.

        Validation:
        - The referenced shift_template must belong to the same tenant+branch.
        """

        tenant_id = ctx.scope.tenant_id

        exists = db.execute(
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
                "branch_id": branch_id,
                "id": shift_template_id,
            },
        ).first()
        if exists is None:
            raise AppError(
                code="roster.shift.not_found",
                message="Shift template not found for branch",
                status_code=404,
            )

        try:
            row = (
                db.execute(
                    sa.text(
                        """
                        INSERT INTO roster.branch_defaults (
                          tenant_id, branch_id, default_shift_template_id
                        ) VALUES (
                          :tenant_id, :branch_id, :shift_template_id
                        )
                        ON CONFLICT (tenant_id, branch_id)
                        DO UPDATE SET default_shift_template_id = EXCLUDED.default_shift_template_id
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "branch_id": branch_id,
                        "shift_template_id": shift_template_id,
                    },
                )
                .mappings()
                .first()
            )
            assert row is not None

            audit_svc.record(
                db,
                ctx=ctx,
                action="roster.default.set",
                entity_type="roster.branch_default",
                entity_id=branch_id,
                before=None,
                after={"default_shift_template_id": str(shift_template_id)},
            )

            db.commit()
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

        return dict(row)

    def get_default_shift(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        branch_id: UUID,
    ) -> dict[str, Any]:
        """Get the branch default shift row (404 if missing)."""

        tenant_id = ctx.scope.tenant_id
        row = (
            db.execute(
                sa.text(
                    """
                    SELECT *
                    FROM roster.branch_defaults
                    WHERE tenant_id = :tenant_id
                      AND branch_id = :branch_id
                    """
                ),
                {"tenant_id": tenant_id, "branch_id": branch_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(
                code="roster.default.not_found",
                message="Default shift not set for branch",
                status_code=404,
            )
        return dict(row)

