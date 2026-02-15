from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterable

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import AttendanceSummary, Dataset, MonthState, PosSummary


@dataclass(frozen=True)
class MobileRow:
    employee_id: uuid.UUID
    employee_code: str
    name: str
    department: str | None

    qty: float | None
    net_sales: float | None
    bills: int | None
    customers: int | None
    return_customers: int | None

    present: int | None
    absent: int | None
    work_minutes: int | None
    stocking_done: int | None
    stocking_missed: int | None


def get_published_dataset_id(
    db: Session, *, tenant_id: uuid.UUID, branch_id: uuid.UUID, month_key: str
) -> uuid.UUID | None:
    return db.execute(
        select(MonthState.published_dataset_id).where(
            MonthState.tenant_id == tenant_id,
            MonthState.branch_id == branch_id,
            MonthState.month_key == month_key,
        )
    ).scalar_one_or_none()


def get_dataset(db: Session, dataset_id: uuid.UUID) -> Dataset | None:
    return db.get(Dataset, dataset_id)


def rows_to_mobile(rows: Iterable[sa.Row]) -> list[MobileRow]:
    out: list[MobileRow] = []
    for r in rows:
        out.append(
            MobileRow(
                employee_id=r.employee_id,
                employee_code=r.employee_code,
                name=r.name,
                department=r.department,
                qty=float(r.qty) if r.qty is not None else None,
                net_sales=float(r.net_sales) if r.net_sales is not None else None,
                bills=r.bills,
                customers=r.customers,
                return_customers=r.return_customers,
                present=r.present,
                absent=r.absent,
                work_minutes=r.work_minutes,
                stocking_done=r.stocking_done,
                stocking_missed=r.stocking_missed,
            )
        )
    return out


def fetch_monthly_rows(
    db: Session,
    *,
    tenant_id: uuid.UUID,
    branch_id: uuid.UUID,
    dataset_id: uuid.UUID,
) -> list[MobileRow]:
    """
    Fetch per-employee monthly aggregates for a dataset by joining POS + Attendance.
    """
    rows = db.execute(
        sa.text(
            """
            WITH ids AS (
              SELECT employee_id
              FROM analytics.pos_summary
              WHERE tenant_id = :tenant_id
                AND dataset_id = :dataset_id
              UNION
              SELECT employee_id
              FROM attendance.attendance_summary
              WHERE tenant_id = :tenant_id
                AND dataset_id = :dataset_id
            ),
            current_employment AS (
              SELECT
                ee.employee_id,
                ee.branch_id,
                ee.org_unit_id,
                ROW_NUMBER() OVER (
                  PARTITION BY ee.employee_id
                  ORDER BY ee.is_primary DESC NULLS LAST, ee.start_date DESC, ee.id DESC
                ) AS rn
              FROM hr_core.employee_employment ee
              WHERE ee.tenant_id = :tenant_id
                AND ee.end_date IS NULL
            ),
            ce AS (
              SELECT * FROM current_employment WHERE rn = 1
            )
            SELECT
              e.id AS employee_id,
              e.employee_code AS employee_code,
              (p.first_name || ' ' || p.last_name) AS name,
              ou.name AS department,
              ps.qty,
              ps.net_sales,
              ps.bills,
              ps.customers,
              ps.return_customers,
              att.present,
              att.absent,
              att.work_minutes,
              att.stocking_done,
              att.stocking_missed
            FROM ids
            JOIN hr_core.employees e ON e.id = ids.employee_id
            JOIN hr_core.persons p ON p.id = e.person_id
            LEFT JOIN analytics.pos_summary ps
              ON ps.dataset_id = :dataset_id
             AND ps.employee_id = ids.employee_id
             AND ps.tenant_id = :tenant_id
            LEFT JOIN attendance.attendance_summary att
              ON att.dataset_id = :dataset_id
             AND att.employee_id = ids.employee_id
             AND att.tenant_id = :tenant_id
            LEFT JOIN ce ON ce.employee_id = e.id AND ce.branch_id = :branch_id
            LEFT JOIN tenancy.org_units ou ON ou.id = ce.org_unit_id
            WHERE e.tenant_id = :tenant_id
            ORDER BY e.employee_code, e.id
            """
        ),
        {"tenant_id": tenant_id, "branch_id": branch_id, "dataset_id": dataset_id},
    ).all()
    return rows_to_mobile(rows)


def iter_employee_ids(rows: Iterable[MobileRow]) -> set[uuid.UUID]:
    return {r.employee_id for r in rows}
