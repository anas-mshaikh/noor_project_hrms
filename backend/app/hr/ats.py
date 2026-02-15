"""
ats.py (HR module - Phase 5)

This module contains *small, testable helpers* for the ATS (Applicant Tracking System)
layer introduced in Phase 5.

Why keep this separate from the router:
- Router code should focus on HTTP request/response handling.
- The ATS defaults and stage-name logic are pure business rules and are easy to unit test.

MVP constraints:
- We do NOT introduce a "candidate identity" table yet.
- Each resume is treated as the applicant (1 resume = 1 application).
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.models.models import HRPipelineStage


@dataclass(frozen=True)
class DefaultStageSpec:
    """
    One default pipeline stage configuration.

    `sort_order` defines Kanban column order.
    """

    name: str
    sort_order: int
    is_terminal: bool = False


DEFAULT_PIPELINE_STAGES: list[DefaultStageSpec] = [
    DefaultStageSpec(name="Applied", sort_order=1),
    DefaultStageSpec(name="Screened", sort_order=2),
    DefaultStageSpec(name="Interview", sort_order=3),
    DefaultStageSpec(name="Offer", sort_order=4),
    DefaultStageSpec(name="Hired", sort_order=5, is_terminal=True),
    DefaultStageSpec(name="Rejected", sort_order=6, is_terminal=True),
]


def normalize_stage_name(name: str) -> str:
    """
    Normalize a stage name for comparisons.

    We keep this intentionally conservative:
    - trim surrounding whitespace
    - collapse internal whitespace
    - casefold to lowercase for case-insensitive matching
    """

    return " ".join((name or "").strip().split()).lower()


def ensure_default_pipeline_stages(db: Session, opening_id: UUID, *, tenant_id: UUID) -> None:
    """
    Ensure an opening has at least the default pipeline stages.

    This is used in two places:
    1) Immediately after creating a new opening (predictable behavior).
    2) Lazily, when accessing ATS endpoints for older openings created before Phase 5.

    Implementation note:
    - This function only INSERTs if the opening has ZERO stages.
    - If some stages already exist, we assume the opening has a customized pipeline
      and we do not attempt to "patch" it.
    """

    exists = (
        db.query(HRPipelineStage.id)
        .filter(HRPipelineStage.opening_id == opening_id, HRPipelineStage.tenant_id == tenant_id)
        .limit(1)
        .first()
        is not None
    )
    if exists:
        return

    for spec in DEFAULT_PIPELINE_STAGES:
        db.add(
            HRPipelineStage(
                tenant_id=tenant_id,
                opening_id=opening_id,
                name=spec.name,
                sort_order=spec.sort_order,
                is_terminal=spec.is_terminal,
            )
        )

    # NOTE: caller owns the transaction (commit/rollback).


def find_stage_by_name(
    db: Session, opening_id: UUID, stage_name: str, *, tenant_id: UUID
) -> HRPipelineStage | None:
    """
    Find a stage by name (case-insensitive) within an opening.

    This supports nicer API ergonomics where callers can pass stage_name.
    """

    needle = normalize_stage_name(stage_name)
    if not needle:
        return None

    return (
        db.query(HRPipelineStage)
        .filter(
            HRPipelineStage.opening_id == opening_id,
            HRPipelineStage.tenant_id == tenant_id,
            sa.func.lower(HRPipelineStage.name) == needle,
        )
        .first()
    )


def list_stage_names(db: Session, opening_id: UUID, *, tenant_id: UUID) -> list[str]:
    """
    Return all stage names for an opening (sorted by sort_order).

    Used for API error messages to keep them actionable.
    """

    rows = (
        db.query(HRPipelineStage.name)
        .filter(HRPipelineStage.opening_id == opening_id, HRPipelineStage.tenant_id == tenant_id)
        .order_by(HRPipelineStage.sort_order.asc())
        .all()
    )
    return [r[0] for r in rows]
