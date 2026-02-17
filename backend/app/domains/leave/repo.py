from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session


def get_leave_type_by_code(db: Session, *, tenant_id: UUID, code: str) -> dict[str, Any] | None:
    row = db.execute(
        sa.text(
            """
            SELECT
              id,
              tenant_id,
              code,
              name,
              is_paid,
              unit,
              requires_attachment,
              allow_negative_balance,
              max_consecutive_days,
              min_notice_days,
              is_active,
              created_at,
              updated_at
            FROM leave.leave_types
            WHERE tenant_id = :tenant_id
              AND code = :code
            """
        ),
        {"tenant_id": tenant_id, "code": code},
    ).mappings().first()
    return dict(row) if row is not None else None


def list_leave_types(db: Session, *, tenant_id: UUID, active_only: bool) -> list[dict[str, Any]]:
    rows = db.execute(
        sa.text(
            """
            SELECT
              id,
              tenant_id,
              code,
              name,
              is_paid,
              unit,
              requires_attachment,
              allow_negative_balance,
              max_consecutive_days,
              min_notice_days,
              is_active,
              created_at,
              updated_at
            FROM leave.leave_types
            WHERE tenant_id = :tenant_id
              AND (:active_only = false OR is_active = true)
            ORDER BY code ASC
            """
        ),
        {"tenant_id": tenant_id, "active_only": active_only},
    ).mappings().all()
    return [dict(r) for r in rows]


def insert_leave_type(db: Session, *, tenant_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
    row = db.execute(
        sa.text(
            """
            INSERT INTO leave.leave_types (
              tenant_id, code, name, is_paid, unit,
              requires_attachment, allow_negative_balance,
              max_consecutive_days, min_notice_days, is_active
            ) VALUES (
              :tenant_id, :code, :name, :is_paid, :unit,
              :requires_attachment, :allow_negative_balance,
              :max_consecutive_days, :min_notice_days, :is_active
            )
            RETURNING *
            """
        ),
        {"tenant_id": tenant_id, **payload},
    ).mappings().first()
    assert row is not None
    return dict(row)


def get_policy_by_id(db: Session, *, tenant_id: UUID, policy_id: UUID) -> dict[str, Any] | None:
    row = db.execute(
        sa.text(
            """
            SELECT *
            FROM leave.leave_policies
            WHERE tenant_id = :tenant_id
              AND id = :id
            """
        ),
        {"tenant_id": tenant_id, "id": policy_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def list_policies(db: Session, *, tenant_id: UUID, company_id: UUID | None, branch_id: UUID | None) -> list[dict[str, Any]]:
    rows = db.execute(
        sa.text(
            """
            SELECT *
            FROM leave.leave_policies
            WHERE tenant_id = :tenant_id
              AND (CAST(:company_id AS uuid) IS NULL OR company_id = :company_id)
              AND (CAST(:branch_id AS uuid) IS NULL OR branch_id = :branch_id)
            ORDER BY updated_at DESC, id DESC
            """
        ),
        {"tenant_id": tenant_id, "company_id": company_id, "branch_id": branch_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def insert_policy(db: Session, *, tenant_id: UUID, payload: dict[str, Any]) -> dict[str, Any]:
    row = db.execute(
        sa.text(
            """
            INSERT INTO leave.leave_policies (
              tenant_id, code, name, company_id, branch_id,
              effective_from, effective_to, year_start_month, is_active
            ) VALUES (
              :tenant_id, :code, :name, :company_id, :branch_id,
              :effective_from, :effective_to, :year_start_month, :is_active
            )
            RETURNING *
            """
        ),
        {"tenant_id": tenant_id, **payload},
    ).mappings().first()
    assert row is not None
    return dict(row)


def upsert_policy_rules(
    db: Session,
    *,
    tenant_id: UUID,
    policy_id: UUID,
    rules: list[dict[str, Any]],
) -> None:
    for r in rules:
        db.execute(
            sa.text(
                """
                INSERT INTO leave.leave_policy_rules (
                  tenant_id, policy_id, leave_type_id,
                  annual_entitlement_days, allow_half_day, requires_attachment
                ) VALUES (
                  :tenant_id, :policy_id, :leave_type_id,
                  :annual_entitlement_days, :allow_half_day, :requires_attachment
                )
                ON CONFLICT (tenant_id, policy_id, leave_type_id)
                DO UPDATE SET
                  annual_entitlement_days = EXCLUDED.annual_entitlement_days,
                  allow_half_day = EXCLUDED.allow_half_day,
                  requires_attachment = EXCLUDED.requires_attachment
                """
            ),
            {"tenant_id": tenant_id, "policy_id": policy_id, **r},
        )


def get_policy_rule(
    db: Session,
    *,
    tenant_id: UUID,
    policy_id: UUID,
    leave_type_id: UUID,
) -> dict[str, Any] | None:
    row = db.execute(
        sa.text(
            """
            SELECT *
            FROM leave.leave_policy_rules
            WHERE tenant_id = :tenant_id
              AND policy_id = :policy_id
              AND leave_type_id = :leave_type_id
            """
        ),
        {"tenant_id": tenant_id, "policy_id": policy_id, "leave_type_id": leave_type_id},
    ).mappings().first()
    return dict(row) if row is not None else None


def get_active_employee_policy_id(
    db: Session,
    *,
    tenant_id: UUID,
    employee_id: UUID,
    at_date: date,
) -> UUID | None:
    row = db.execute(
        sa.text(
            """
            SELECT policy_id
            FROM leave.employee_leave_policy
            WHERE tenant_id = :tenant_id
              AND employee_id = :employee_id
              AND effective_from <= :at_date
              AND (effective_to IS NULL OR effective_to >= :at_date)
            ORDER BY effective_from DESC, id DESC
            LIMIT 1
            """
        ),
        {"tenant_id": tenant_id, "employee_id": employee_id, "at_date": at_date},
    ).first()
    return UUID(str(row[0])) if row is not None else None


def assign_employee_policy(
    db: Session,
    *,
    tenant_id: UUID,
    employee_id: UUID,
    policy_id: UUID,
    effective_from: date,
    effective_to: date | None,
) -> None:
    # Close any currently-active assignment.
    db.execute(
        sa.text(
            """
            UPDATE leave.employee_leave_policy
            SET effective_to = :effective_from_minus1
            WHERE tenant_id = :tenant_id
              AND employee_id = :employee_id
              AND effective_to IS NULL
            """
        ),
        {
            "tenant_id": tenant_id,
            "employee_id": employee_id,
            "effective_from_minus1": effective_from.fromordinal(effective_from.toordinal() - 1),
        },
    )
    db.execute(
        sa.text(
            """
            INSERT INTO leave.employee_leave_policy (
              tenant_id, employee_id, policy_id, effective_from, effective_to
            ) VALUES (
              :tenant_id, :employee_id, :policy_id, :effective_from, :effective_to
            )
            """
        ),
        {
            "tenant_id": tenant_id,
            "employee_id": employee_id,
            "policy_id": policy_id,
            "effective_from": effective_from,
            "effective_to": effective_to,
        },
    )


def list_weekly_off(db: Session, *, tenant_id: UUID, branch_id: UUID) -> list[dict[str, Any]]:
    rows = db.execute(
        sa.text(
            """
            SELECT weekday, is_off
            FROM leave.weekly_off
            WHERE tenant_id = :tenant_id
              AND branch_id = :branch_id
            ORDER BY weekday ASC
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    ).mappings().all()
    return [dict(r) for r in rows]


def replace_weekly_off(
    db: Session,
    *,
    tenant_id: UUID,
    branch_id: UUID,
    days: list[dict[str, Any]],
) -> None:
    db.execute(
        sa.text("DELETE FROM leave.weekly_off WHERE tenant_id = :tenant_id AND branch_id = :branch_id"),
        {"tenant_id": tenant_id, "branch_id": branch_id},
    )
    for d in days:
        db.execute(
            sa.text(
                """
                INSERT INTO leave.weekly_off (tenant_id, branch_id, weekday, is_off)
                VALUES (:tenant_id, :branch_id, :weekday, :is_off)
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id, **d},
        )


def list_holidays(
    db: Session,
    *,
    tenant_id: UUID,
    branch_id: UUID | None,
    from_day: date | None,
    to_day: date | None,
) -> list[dict[str, Any]]:
    rows = db.execute(
        sa.text(
            """
            SELECT id, tenant_id, branch_id, day, name, created_at
            FROM leave.holidays
            WHERE tenant_id = :tenant_id
              AND (CAST(:branch_id AS uuid) IS NULL OR branch_id = :branch_id OR branch_id IS NULL)
              AND (CAST(:from_day AS date) IS NULL OR day >= :from_day)
              AND (CAST(:to_day AS date) IS NULL OR day <= :to_day)
            ORDER BY day ASC, id ASC
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id, "from_day": from_day, "to_day": to_day},
    ).mappings().all()
    return [dict(r) for r in rows]


def insert_holiday(db: Session, *, tenant_id: UUID, branch_id: UUID | None, day: date, name: str) -> dict[str, Any]:
    row = db.execute(
        sa.text(
            """
            INSERT INTO leave.holidays (tenant_id, company_id, branch_id, day, name)
            VALUES (:tenant_id, NULL, :branch_id, :day, :name)
            RETURNING id, tenant_id, branch_id, day, name, created_at
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id, "day": day, "name": name},
    ).mappings().first()
    assert row is not None
    return dict(row)


def get_balance(
    db: Session,
    *,
    tenant_id: UUID,
    employee_id: UUID,
    leave_type_id: UUID,
    period_year: int,
) -> Decimal:
    raw = db.execute(
        sa.text(
            """
            SELECT COALESCE(SUM(delta_days), 0)
            FROM leave.leave_ledger
            WHERE tenant_id = :tenant_id
              AND employee_id = :employee_id
              AND leave_type_id = :leave_type_id
              AND period_year = :period_year
            """
        ),
        {
            "tenant_id": tenant_id,
            "employee_id": employee_id,
            "leave_type_id": leave_type_id,
            "period_year": int(period_year),
        },
    ).scalar()
    try:
        return Decimal(str(raw))
    except Exception:
        return Decimal(0)


def insert_ledger_row(
    db: Session,
    *,
    tenant_id: UUID,
    employee_id: UUID,
    leave_type_id: UUID,
    period_year: int,
    delta_days: Decimal,
    source_type: str,
    source_id: UUID | None,
    note: str | None,
    created_by_user_id: UUID | None,
    idempotent_for_leave_request: bool,
) -> UUID:
    row = db.execute(
        sa.text(
            f"""
            INSERT INTO leave.leave_ledger (
              tenant_id, employee_id, leave_type_id, period_year,
              delta_days, source_type, source_id, note, created_by_user_id
            ) VALUES (
              :tenant_id, :employee_id, :leave_type_id, :period_year,
              :delta_days, :source_type, :source_id, :note, :created_by_user_id
            )
            { 'ON CONFLICT DO NOTHING' if idempotent_for_leave_request else '' }
            RETURNING id
            """
        ),
        {
            "tenant_id": tenant_id,
            "employee_id": employee_id,
            "leave_type_id": leave_type_id,
            "period_year": int(period_year),
            "delta_days": delta_days,
            "source_type": source_type,
            "source_id": source_id,
            "note": note,
            "created_by_user_id": created_by_user_id,
        },
    ).first()
    if row is None:
        # Idempotent insert hit conflict.
        existing = db.execute(
            sa.text(
                """
                SELECT id
                FROM leave.leave_ledger
                WHERE tenant_id = :tenant_id
                  AND source_type = :source_type
                  AND source_id = :source_id
                  AND leave_type_id = :leave_type_id
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
            ),
            {
                "tenant_id": tenant_id,
                "source_type": source_type,
                "source_id": source_id,
                "leave_type_id": leave_type_id,
            },
        ).first()
        assert existing is not None
        return UUID(str(existing[0]))
    return UUID(str(row[0]))

