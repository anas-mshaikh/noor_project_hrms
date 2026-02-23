"""
Payroll calendar/period services (Milestone 9).

v1 focuses on monthly calendars with explicit periods (`YYYY-MM`).
Periods are stored as inclusive ranges [start_date, end_date].
"""

from __future__ import annotations

import re
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.shared.types import AuthContext


_PERIOD_KEY_RE = re.compile(r"^[0-9]{4}-[0-9]{2}$")


def _validate_period_key(period_key: str) -> None:
    if not _PERIOD_KEY_RE.match(period_key or ""):
        raise AppError(
            code="payroll.period.invalid_key",
            message="period_key must be in format YYYY-MM",
            status_code=400,
        )


class PayrollCalendarService:
    """Create/list payroll calendars and periods (tenant-scoped)."""

    def create_calendar(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        code: str,
        name: str,
        currency_code: str,
        timezone: str,
        is_active: bool,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id

        try:
            row = (
                db.execute(
                    sa.text(
                        """
                        INSERT INTO payroll.calendars (
                          tenant_id,
                          code,
                          name,
                          frequency,
                          currency_code,
                          timezone,
                          is_active,
                          created_by_user_id
                        ) VALUES (
                          :tenant_id,
                          :code,
                          :name,
                          'MONTHLY',
                          :currency_code,
                          :timezone,
                          :is_active,
                          :created_by_user_id
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "code": code,
                        "name": name,
                        "currency_code": currency_code,
                        "timezone": timezone,
                        "is_active": bool(is_active),
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
                action="payroll.calendar.create",
                entity_type="payroll.calendar",
                entity_id=UUID(str(row["id"])),
                before=None,
                after={
                    "code": str(code),
                    "name": str(name),
                    "currency_code": str(currency_code),
                    "timezone": str(timezone),
                    "is_active": bool(is_active),
                },
            )

            db.commit()
            return dict(row)
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="validation_error",
                message="Calendar code already exists",
                status_code=409,
            ) from e
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

    def list_calendars(
        self,
        db: Session,
        *,
        ctx: AuthContext,
    ) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id
        rows = (
            db.execute(
                sa.text(
                    """
                    SELECT *
                    FROM payroll.calendars
                    WHERE tenant_id = :tenant_id
                    ORDER BY is_active DESC, code ASC, created_at ASC, id ASC
                    """
                ),
                {"tenant_id": tenant_id},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def create_period(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        calendar_id: UUID,
        period_key: str,
        start_date,
        end_date,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        _validate_period_key(period_key)

        if start_date > end_date:
            raise AppError(
                code="validation_error",
                message="start_date must be <= end_date",
                status_code=400,
            )

        cal = db.execute(
            sa.text(
                """
                SELECT id
                FROM payroll.calendars
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": calendar_id},
        ).first()
        if cal is None:
            raise AppError(
                code="payroll.calendar.not_found",
                message="Calendar not found",
                status_code=404,
            )

        try:
            row = (
                db.execute(
                    sa.text(
                        """
                        INSERT INTO payroll.periods (
                          tenant_id,
                          calendar_id,
                          period_key,
                          start_date,
                          end_date,
                          status
                        ) VALUES (
                          :tenant_id,
                          :calendar_id,
                          :period_key,
                          :start_date,
                          :end_date,
                          'OPEN'
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "calendar_id": calendar_id,
                        "period_key": period_key,
                        "start_date": start_date,
                        "end_date": end_date,
                    },
                )
                .mappings()
                .first()
            )
            assert row is not None

            audit_svc.record(
                db,
                ctx=ctx,
                action="payroll.period.create",
                entity_type="payroll.period",
                entity_id=UUID(str(row["id"])),
                before=None,
                after={
                    "calendar_id": str(calendar_id),
                    "period_key": str(period_key),
                    "start_date": str(start_date),
                    "end_date": str(end_date),
                },
            )

            db.commit()
            return dict(row)
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="validation_error",
                message="Period already exists for calendar",
                status_code=409,
            ) from e
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

    def list_periods_by_year(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        calendar_id: UUID,
        year: int,
    ) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id
        prefix = f"{int(year):04d}-"

        rows = (
            db.execute(
                sa.text(
                    """
                    SELECT *
                    FROM payroll.periods
                    WHERE tenant_id = :tenant_id
                      AND calendar_id = :calendar_id
                      AND period_key LIKE :prefix
                    ORDER BY period_key ASC, start_date ASC, id ASC
                    """
                ),
                {"tenant_id": tenant_id, "calendar_id": calendar_id, "prefix": f"{prefix}%"},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def get_period(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        calendar_id: UUID,
        period_key: str,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        _validate_period_key(period_key)

        row = (
            db.execute(
                sa.text(
                    """
                    SELECT *
                    FROM payroll.periods
                    WHERE tenant_id = :tenant_id
                      AND calendar_id = :calendar_id
                      AND period_key = :period_key
                    """
                ),
                {"tenant_id": tenant_id, "calendar_id": calendar_id, "period_key": period_key},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(
                code="payroll.period.not_found",
                message="Period not found",
                status_code=404,
            )
        return dict(row)

