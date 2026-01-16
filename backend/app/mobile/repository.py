from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Iterable

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.models import (
    AttendanceSummary,
    Dataset,
    MonthState,
    Organization,
    PosSummary,
    Salesman,
    Store,
)


@dataclass(frozen=True)
class MobileRow:
    salesman_id: str
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


def get_published_dataset_id(db: Session, month_key: str) -> uuid.UUID | None:
    return db.execute(
        select(MonthState.published_dataset_id).where(MonthState.month_key == month_key)
    ).scalar_one_or_none()


def get_dataset(db: Session, dataset_id: uuid.UUID) -> Dataset | None:
    return db.get(Dataset, dataset_id)


def resolve_store_org(db: Session, store_id: uuid.UUID) -> tuple[Store, Organization]:
    store = db.get(Store, store_id)
    if store is None:
        raise ValueError(f"store not found: {store_id}")
    org = db.get(Organization, store.org_id)
    if org is None:
        raise ValueError(f"organization not found: {store.org_id}")
    return store, org


def infer_single_store(db: Session) -> Store | None:
    store_count = db.execute(select(sa.func.count()).select_from(Store)).scalar_one()
    if int(store_count or 0) != 1:
        return None
    return db.execute(select(Store).limit(1)).scalar_one_or_none()


def rows_to_mobile(rows: Iterable[sa.Row]) -> list[MobileRow]:
    out: list[MobileRow] = []
    for r in rows:
        out.append(
            MobileRow(
                salesman_id=r.salesman_id,
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


def fetch_monthly_rows(db: Session, dataset_id: uuid.UUID) -> list[MobileRow]:
    """
    Fetch per-salesman monthly aggregates for a dataset by joining POS + Attendance.
    """
    pos_ids = select(PosSummary.salesman_id).where(PosSummary.dataset_id == dataset_id)
    att_ids = select(AttendanceSummary.salesman_id).where(
        AttendanceSummary.dataset_id == dataset_id
    )
    ids_subq = sa.union(pos_ids, att_ids).subquery()

    q = (
        select(
            Salesman.salesman_id,
            Salesman.name,
            Salesman.department,
            PosSummary.qty,
            PosSummary.net_sales,
            PosSummary.bills,
            PosSummary.customers,
            PosSummary.return_customers,
            AttendanceSummary.present,
            AttendanceSummary.absent,
            AttendanceSummary.work_minutes,
            AttendanceSummary.stocking_done,
            AttendanceSummary.stocking_missed,
        )
        .select_from(ids_subq)
        .join(Salesman, Salesman.salesman_id == ids_subq.c.salesman_id)
        .join(
            PosSummary,
            (PosSummary.salesman_id == ids_subq.c.salesman_id)
            & (PosSummary.dataset_id == dataset_id),
            isouter=True,
        )
        .join(
            AttendanceSummary,
            (AttendanceSummary.salesman_id == ids_subq.c.salesman_id)
            & (AttendanceSummary.dataset_id == dataset_id),
            isouter=True,
        )
    )

    rows = db.execute(q).all()
    return rows_to_mobile(rows)


def iter_salesman_ids(rows: Iterable[MobileRow]) -> set[str]:
    return {r.salesman_id for r in rows}
