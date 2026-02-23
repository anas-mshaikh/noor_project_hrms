"""
Payroll export services (Milestone 9).

v1 provides a simple CSV export for payrun items (bank/accounting integrations
are out of scope).
"""

from __future__ import annotations

import csv
import io
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.shared.types import AuthContext


class PayrunExportService:
    """Export payruns in basic CSV formats (placeholder for v1)."""

    def export_payrun_csv(self, db: Session, *, ctx: AuthContext, payrun_id: UUID) -> bytes:
        tenant_id = ctx.scope.tenant_id

        payrun = (
            db.execute(
                sa.text(
                    """
                    SELECT id, branch_id
                    FROM payroll.payruns
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                    """
                ),
                {"tenant_id": tenant_id, "id": payrun_id},
            )
            .mappings()
            .first()
        )
        if payrun is None:
            raise AppError(code="payroll.payrun.not_found", message="Payrun not found", status_code=404)

        if ctx.scope.branch_id is not None and UUID(str(payrun["branch_id"])) != ctx.scope.branch_id:
            raise AppError(code="payroll.payrun.not_found", message="Payrun not found", status_code=404)

        rows = (
            db.execute(
                sa.text(
                    """
                    SELECT
                      i.employee_id,
                      e.employee_code,
                      i.payable_days,
                      i.gross_amount,
                      i.deductions_amount,
                      i.net_amount,
                      i.status
                    FROM payroll.payrun_items i
                    JOIN hr_core.employees e
                      ON e.id = i.employee_id
                     AND e.tenant_id = i.tenant_id
                    WHERE i.tenant_id = :tenant_id
                      AND i.payrun_id = :payrun_id
                    ORDER BY e.employee_code ASC NULLS LAST, i.employee_id ASC
                    """
                ),
                {"tenant_id": tenant_id, "payrun_id": payrun_id},
            )
            .mappings()
            .all()
        )

        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(
            [
                "employee_id",
                "employee_code",
                "payable_days",
                "gross_amount",
                "deductions_amount",
                "net_amount",
                "status",
            ]
        )
        for r in rows:
            w.writerow(
                [
                    str(r["employee_id"]),
                    str(r["employee_code"] or ""),
                    int(r["payable_days"] or 0),
                    str(r["gross_amount"]),
                    str(r["deductions_amount"]),
                    str(r["net_amount"]),
                    str(r["status"]),
                ]
            )

        return buf.getvalue().encode("utf-8")

