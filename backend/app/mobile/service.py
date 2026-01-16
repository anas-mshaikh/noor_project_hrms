from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.core.config import settings
from app.mobile import firestore_sync
from app.mobile.repository import MobileRow, fetch_monthly_rows
from app.mobile.schemas import (
    LeaderboardDocV1,
    LeaderboardEntryV1,
    MonthlyEmployeeStatsV1,
    MobileLeaderboardPreviewOut,
    MobileSyncPreviewOut,
)
from app.models.models import Dataset

logger = logging.getLogger(__name__)


@dataclass
class RankedRow:
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

    rank_overall: int = 0
    rank_department: int = 0


def _metric_or_zero(value: float | int | None) -> float:
    return float(value) if value is not None else 0.0


def _sort_key(row: RankedRow) -> tuple[float, float, float, str]:
    return (
        -_metric_or_zero(row.net_sales),
        -_metric_or_zero(row.bills),
        -_metric_or_zero(row.customers),
        row.salesman_id,
    )


def _department_key(dept: str | None) -> str:
    if not dept:
        return "unknown"
    return "-".join(str(dept).strip().lower().split())


def rank_rows(rows: Iterable[MobileRow]) -> list[RankedRow]:
    ranked = [
        RankedRow(
            salesman_id=r.salesman_id,
            name=r.name,
            department=r.department,
            qty=r.qty,
            net_sales=r.net_sales,
            bills=r.bills,
            customers=r.customers,
            return_customers=r.return_customers,
            present=r.present,
            absent=r.absent,
            work_minutes=r.work_minutes,
            stocking_done=r.stocking_done,
            stocking_missed=r.stocking_missed,
        )
        for r in rows
    ]

    # Overall ranking
    overall_sorted = sorted(ranked, key=_sort_key)
    for idx, row in enumerate(overall_sorted, start=1):
        row.rank_overall = idx

    # Department ranking
    by_dept: dict[str, list[RankedRow]] = {}
    for row in ranked:
        by_dept.setdefault(_department_key(row.department), []).append(row)

    for dept_rows in by_dept.values():
        dept_sorted = sorted(dept_rows, key=_sort_key)
        for idx, row in enumerate(dept_sorted, start=1):
            row.rank_department = idx

    return ranked


def build_leaderboards(
    ranked_rows: list[RankedRow],
    *,
    month_key: str,
    limit: int = 50,
) -> tuple[LeaderboardDocV1, dict[str, LeaderboardDocV1]]:
    now = datetime.now(timezone.utc)
    overall_sorted = sorted(ranked_rows, key=_sort_key)[:limit]
    overall_entries = [
        LeaderboardEntryV1(
            rank=row.rank_overall,
            salesman_id=row.salesman_id,
            name=row.name,
            department=row.department,
            metric_value=_metric_or_zero(row.net_sales),
        )
        for row in overall_sorted
    ]
    overall = LeaderboardDocV1(
        month_key=month_key,
        metric="net_sales",
        updated_at=now,
        top=overall_entries,
    )

    dept_docs: dict[str, LeaderboardDocV1] = {}
    by_dept: dict[str, list[RankedRow]] = {}
    for row in ranked_rows:
        by_dept.setdefault(_department_key(row.department), []).append(row)

    for dept_key, dept_rows in by_dept.items():
        dept_sorted = sorted(dept_rows, key=_sort_key)[:limit]
        entries = [
            LeaderboardEntryV1(
                rank=row.rank_department,
                salesman_id=row.salesman_id,
                name=row.name,
                department=row.department,
                metric_value=_metric_or_zero(row.net_sales),
            )
            for row in dept_sorted
        ]
        dept_docs[dept_key] = LeaderboardDocV1(
            month_key=month_key,
            metric="net_sales",
            updated_at=now,
            top=entries,
        )

    return overall, dept_docs


def build_mobile_stats(
    *,
    month_key: str,
    dataset_id: uuid.UUID,
    store_id: uuid.UUID,
    org_id: uuid.UUID,
    rows: list[MobileRow],
) -> list[MonthlyEmployeeStatsV1]:
    ranked_rows = rank_rows(rows)
    synced_at = datetime.now(timezone.utc)
    stats: list[MonthlyEmployeeStatsV1] = []

    for row in ranked_rows:
        stats.append(
            MonthlyEmployeeStatsV1(
                month_key=month_key,
                published_dataset_id=str(dataset_id),
                store_id=str(store_id),
                org_id=str(org_id),
                salesman_id=row.salesman_id,
                name=row.name,
                department=row.department,
                qty=row.qty,
                net_sales=row.net_sales,
                bills=row.bills,
                customers=row.customers,
                return_customers=row.return_customers,
                present=row.present,
                absent=row.absent,
                work_minutes=row.work_minutes,
                stocking_done=row.stocking_done,
                stocking_missed=row.stocking_missed,
                rank_overall=row.rank_overall,
                rank_department=row.rank_department,
                dataset_id=str(dataset_id),
                synced_at=synced_at,
            )
        )

    return stats


def build_mobile_payload(
    db: Session,
    *,
    month_key: str,
    dataset_id: uuid.UUID,
    store_id: uuid.UUID,
    org_id: uuid.UUID,
) -> tuple[list[MonthlyEmployeeStatsV1], LeaderboardDocV1, dict[str, LeaderboardDocV1]]:
    rows = fetch_monthly_rows(db, dataset_id)
    ranked_rows = rank_rows(rows)
    stats = build_mobile_stats(
        month_key=month_key,
        dataset_id=dataset_id,
        store_id=store_id,
        org_id=org_id,
        rows=rows,
    )
    overall, departments = build_leaderboards(
        ranked_rows,
        month_key=month_key,
        limit=settings.mobile_sync_leaderboard_limit,
    )
    return stats, overall, departments


def sync_mobile_for_dataset(
    db: Session,
    *,
    dataset: Dataset,
    month_key: str,
    store_id: uuid.UUID,
    org_id: uuid.UUID,
    dry_run: bool = False,
) -> tuple[int, int]:
    stats, overall, departments = build_mobile_payload(
        db,
        month_key=month_key,
        dataset_id=dataset.id,
        store_id=store_id,
        org_id=org_id,
    )
    logger.info(
        "mobile sync: month=%s dataset=%s store=%s employees=%s",
        month_key,
        dataset.id,
        store_id,
        len(stats),
    )
    if settings.mobile_sync_enabled:
        firestore_sync.sync_month(
            month_key=month_key,
            dataset_id=dataset.id,
            store_id=store_id,
            org_id=org_id,
            stats=stats,
            overall=overall,
            departments=departments,
            dry_run=dry_run,
        )
    return (len(stats), len(departments))


def preview_mobile_payload(
    db: Session,
    *,
    month_key: str,
    dataset_id: uuid.UUID,
    store_id: uuid.UUID,
    org_id: uuid.UUID,
    limit: int = 20,
) -> MobileSyncPreviewOut:
    rows = fetch_monthly_rows(db, dataset_id)
    stats = build_mobile_stats(
        month_key=month_key,
        dataset_id=dataset_id,
        store_id=store_id,
        org_id=org_id,
        rows=rows,
    )
    return MobileSyncPreviewOut(
        month_key=month_key,
        store_id=str(store_id),
        org_id=str(org_id),
        published_dataset_id=str(dataset_id),
        employees=stats[:limit],
    )


def preview_leaderboards(
    db: Session,
    *,
    month_key: str,
    dataset_id: uuid.UUID,
    store_id: uuid.UUID,
    org_id: uuid.UUID,
) -> MobileLeaderboardPreviewOut:
    rows = fetch_monthly_rows(db, dataset_id)
    ranked_rows = rank_rows(rows)
    overall, departments = build_leaderboards(ranked_rows, month_key=month_key)
    return MobileLeaderboardPreviewOut(
        month_key=month_key,
        store_id=str(store_id),
        org_id=str(org_id),
        published_dataset_id=str(dataset_id),
        overall=overall,
        departments=departments,
    )
