import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.mobile.firebase_admin import get_firestore_client
from app.mobile.schemas import LeaderboardDocV1, MonthlyEmployeeStatsV1

logger = logging.getLogger(__name__)


def _chunked(items: list[Any], n: int) -> list[list[Any]]:
    return [items[i : i + n] for i in range(0, len(items), n)]


def sync_month(
    *,
    month_key: str,
    dataset_id: UUID,
    store_id: UUID,
    org_id: UUID,
    stats: list[MonthlyEmployeeStatsV1],
    overall: LeaderboardDocV1,
    departments: dict[str, LeaderboardDocV1],
    dry_run: bool = False,
) -> None:
    """
    Write mobile-ready docs to Firestore.

    Target structure:
      orgs/{orgId}/stores/{storeId}/months/{YYYY-MM}/employees/{employee_code}
      orgs/{orgId}/stores/{storeId}/months/{YYYY-MM}/leaderboards/overall
      orgs/{orgId}/stores/{storeId}/months/{YYYY-MM}/leaderboards/dept-{departmentKey}
      orgs/{orgId}/stores/{storeId}/months/{YYYY-MM} (metadata)
    """
    synced_at = datetime.now(timezone.utc)

    if dry_run:
        logger.info(
            "mobile sync dry-run: month=%s store=%s org=%s employees=%s departments=%s",
            month_key,
            store_id,
            org_id,
            len(stats),
            len(departments),
        )
        return

    client = get_firestore_client()

    base = (
        client.collection("orgs")
        .document(str(org_id))
        .collection("stores")
        .document(str(store_id))
        .collection("months")
        .document(month_key)
    )

    # Metadata doc for the month
    base.set(
        {
            "published_dataset_id": str(dataset_id),
            "updated_at": synced_at,
        }
    )

    # Employees (batched)
    employees_coll = base.collection("employees")
    for batch_rows in _chunked(stats, 450):
        batch = client.batch()
        for row in batch_rows:
            doc = employees_coll.document(row.employee_code)
            payload = row.model_dump()
            payload["synced_at"] = synced_at
            batch.set(doc, payload)
        batch.commit()

    # Overall leaderboard
    leaderboards = base.collection("leaderboards")
    leaderboards.document("overall").set(overall.model_dump())

    # Department leaderboards (one doc per department)
    for dept_key, doc in departments.items():
        leaderboards.document(f"dept-{dept_key}").set(doc.model_dump())

    logger.info(
        "mobile sync done: month=%s store=%s org=%s employees=%s departments=%s",
        month_key,
        store_id,
        org_id,
        len(stats),
        len(departments),
    )
