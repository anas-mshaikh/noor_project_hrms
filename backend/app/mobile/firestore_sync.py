from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from app.core.config import settings
from app.mobile.schemas import LeaderboardDocV1, MonthlyEmployeeStatsV1

logger = logging.getLogger(__name__)


def _load_service_account_info() -> dict[str, Any]:
    if settings.firebase_service_account_json:
        raw = settings.firebase_service_account_json.strip()
        decoded = base64.b64decode(raw)
        return json.loads(decoded)

    if settings.firebase_service_account_path:
        with open(settings.firebase_service_account_path, "r", encoding="utf-8") as f:
            return json.load(f)

    raise RuntimeError(
        "Firebase service account missing. Set FIREBASE_SERVICE_ACCOUNT_JSON or "
        "FIREBASE_SERVICE_ACCOUNT_PATH."
    )


def _get_firestore_client():
    try:
        import firebase_admin  # type: ignore
        from firebase_admin import credentials, firestore  # type: ignore
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"firebase-admin is required for mobile sync. ({e})") from e

    if not firebase_admin._apps:  # type: ignore[attr-defined]
        info = _load_service_account_info()
        cred = credentials.Certificate(info)
        firebase_admin.initialize_app(cred)

    return firestore.client()


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

    client = _get_firestore_client()

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
