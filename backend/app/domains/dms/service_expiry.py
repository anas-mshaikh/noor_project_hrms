"""
Expiry rules/reporting for DMS documents.

Milestone 5 splits "rules + reporting" (API) from "event generation + notify"
(worker) to keep the API fast and the worker idempotent.
"""

from __future__ import annotations


from datetime import date, timedelta
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.shared.types import AuthContext


class DmsExpiryService:
    # ------------------------------------------------------------------
    # Rules
    # ------------------------------------------------------------------
    def list_rules(self, db: Session, *, ctx: AuthContext) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id
        rows = (
            db.execute(
                sa.text(
                    """
                SELECT
                  r.id,
                  r.tenant_id,
                  r.document_type_id,
                  dt.code AS document_type_code,
                  dt.name AS document_type_name,
                  r.days_before,
                  r.is_active,
                  r.created_at,
                  r.updated_at
                FROM dms.expiry_rules r
                LEFT JOIN dms.document_types dt ON dt.id = r.document_type_id
                WHERE r.tenant_id = :tenant_id
                ORDER BY r.created_at DESC, r.id DESC
                """
                ),
                {"tenant_id": tenant_id},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def create_rule(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        document_type_code: str,
        days_before: int,
        is_active: bool,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id

        dt = db.execute(
            sa.text(
                """
                SELECT id
                FROM dms.document_types
                WHERE tenant_id = :tenant_id
                  AND code = :code
                """
            ),
            {"tenant_id": tenant_id, "code": document_type_code},
        ).first()
        if dt is None:
            raise AppError(
                code="dms.document_type.not_found",
                message="Document type not found",
                status_code=404,
            )
        document_type_id = UUID(str(dt[0]))

        rule_id = uuid4()

        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO dms.expiry_rules (
                      id, tenant_id, document_type_id, days_before, notify_roles, is_active
                    ) VALUES (
                      :id, :tenant_id, :document_type_id, :days_before, '{}'::text[], :is_active
                    )
                    """
                ),
                {
                    "id": rule_id,
                    "tenant_id": tenant_id,
                    "document_type_id": document_type_id,
                    "days_before": int(days_before),
                    "is_active": bool(is_active),
                },
            )

            audit_svc.record(
                db,
                ctx=ctx,
                action="dms.expiry_rule.create",
                entity_type="dms.expiry_rule",
                entity_id=rule_id,
                before=None,
                after={
                    "document_type_code": document_type_code,
                    "days_before": int(days_before),
                    "is_active": bool(is_active),
                },
            )

            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="dms.expiry.rule.duplicate",
                message="Expiry rule already exists",
                status_code=409,
            ) from e

        row = (
            db.execute(
                sa.text(
                    """
                SELECT
                  r.id,
                  r.tenant_id,
                  r.document_type_id,
                  dt.code AS document_type_code,
                  dt.name AS document_type_name,
                  r.days_before,
                  r.is_active,
                  r.created_at,
                  r.updated_at
                FROM dms.expiry_rules r
                LEFT JOIN dms.document_types dt ON dt.id = r.document_type_id
                WHERE r.id = :id
                  AND r.tenant_id = :tenant_id
                """
                ),
                {"id": rule_id, "tenant_id": tenant_id},
            )
            .mappings()
            .first()
        )
        return dict(row) if row is not None else {}

    # ------------------------------------------------------------------
    # Upcoming report
    # ------------------------------------------------------------------
    def upcoming(
        self, db: Session, *, ctx: AuthContext, days: int
    ) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id
        today = date.today()
        end = today + timedelta(days=int(days))

        rows = (
            db.execute(
                sa.text(
                    """
                SELECT
                  d.id AS document_id,
                  dt.code AS document_type_code,
                  dt.name AS document_type_name,
                  d.owner_employee_id,
                  d.expires_at,
                  d.status
                FROM dms.documents d
                JOIN dms.document_types dt ON dt.id = d.document_type_id
                WHERE d.tenant_id = :tenant_id
                  AND d.expires_at IS NOT NULL
                  AND d.expires_at >= :today
                  AND d.expires_at <= :end
                ORDER BY d.expires_at ASC, d.id ASC
                """
                ),
                {"tenant_id": tenant_id, "today": today, "end": end},
            )
            .mappings()
            .all()
        )

        out: list[dict[str, Any]] = []
        for r in rows:
            expires_at = r["expires_at"]
            if expires_at is None:
                continue
            out.append(
                {
                    "document_id": r["document_id"],
                    "document_type_code": r["document_type_code"],
                    "document_type_name": r["document_type_name"],
                    "owner_employee_id": r["owner_employee_id"],
                    "expires_at": expires_at,
                    "days_left": int((expires_at - today).days),
                    "status": r["status"],
                }
            )
        return out
