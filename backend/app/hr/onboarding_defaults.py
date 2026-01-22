"""
onboarding_defaults.py (HR module - Phase 6)

This module contains the default onboarding checklist used when converting a
HIRED ATS application into a canonical Employee + onboarding plan.

Why keep defaults in a separate module:
- Router code stays focused on HTTP handling.
- The checklist is an explicit, testable product decision.
- Later, you can make this configurable per store without rewriting the router.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.models import HROnboardingTask


@dataclass(frozen=True)
class DefaultOnboardingTaskSpec:
    """
    One default onboarding task template.

    Notes:
    - `task_type` is a lightweight UI hint (TASK | DOCUMENT | ACTION).
    - `metadata_json` is stored on the task row so the UI can understand
      structure without hardcoding task titles.
    """

    title: str
    task_type: str = "TASK"
    metadata_json: dict[str, Any] = field(default_factory=dict)


DEFAULT_ONBOARDING_TASKS: list[DefaultOnboardingTaskSpec] = [
    # Document collection
    DefaultOnboardingTaskSpec(
        title="Upload ID document",
        task_type="DOCUMENT",
        metadata_json={"doc_type": "ID"},
    ),
    DefaultOnboardingTaskSpec(
        title="Upload signed contract",
        task_type="DOCUMENT",
        metadata_json={"doc_type": "CONTRACT"},
    ),
    DefaultOnboardingTaskSpec(
        title="Collect bank details",
        task_type="DOCUMENT",
        metadata_json={"doc_type": "BANK"},
    ),
    # Actions / coordination
    DefaultOnboardingTaskSpec(
        title="Provision mobile access",
        task_type="ACTION",
        metadata_json={
            # This endpoint exists already (mobile bootstrap mapping module).
            "endpoint_hint": "/api/v1/stores/{store_id}/employees/{employee_id}/mobile/provision"
        },
    ),
    DefaultOnboardingTaskSpec(title="Assign role / department", task_type="TASK"),
    DefaultOnboardingTaskSpec(title="Verify documents", task_type="TASK"),
]


def insert_default_onboarding_tasks(db: Session, *, plan_id: UUID) -> None:
    """
    Insert the default onboarding tasks for a new plan.

    Transaction behavior:
    - This function does NOT commit; caller owns commit/rollback.
    """

    for idx, spec in enumerate(DEFAULT_ONBOARDING_TASKS, start=1):
        db.add(
            HROnboardingTask(
                plan_id=plan_id,
                title=spec.title,
                task_type=spec.task_type,
                # Keep status explicit so future defaults don't depend on DB defaults.
                status="PENDING",
                sort_order=idx,
                metadata_json=spec.metadata_json,
            )
        )

