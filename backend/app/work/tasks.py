from __future__ import annotations

"""
RQ job entrypoints for the Work module (Auto Task Assignment - Phase 1).

These functions are intentionally small wrappers around the service layer so:
- RQ jobs remain serializable and easy to retry
- core logic stays testable
"""

import logging
from datetime import date
from uuid import UUID

from app.db.session import SessionLocal
from app.work.service import AutoTaskAssigner

logger = logging.getLogger(__name__)


def assign_tasks_job(*, store_id: str, business_date: str) -> dict[str, int]:
    """
    Assign all pending tasks for one store for the given business date (YYYY-MM-DD).

    Idempotency:
    - Only tasks in status='pending' are considered.
    - On successful assignment, the task becomes status='assigned'.

    Returns a small summary dict suitable for logging/monitoring.
    """
    sid = UUID(store_id)
    bdate = date.fromisoformat(business_date)

    db = SessionLocal()
    try:
        svc = AutoTaskAssigner(db)
        summary = svc.assign_pending_tasks_for_store(store_id=sid, business_date=bdate)
        logger.info(
            "work.assign_tasks_job complete store_id=%s business_date=%s summary=%s",
            store_id,
            business_date,
            summary,
        )
        return summary
    finally:
        db.close()

