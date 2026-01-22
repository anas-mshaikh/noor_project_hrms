"""
screening_runs.py (HR module - Phase 3)

This router adds an async "ScreeningRun" pipeline for HR:
- Retrieve Top-K resumes via pgvector embeddings (Phase 2)
- Rerank candidate pool using a local BGE reranker (Phase 3)
- Persist ranked results for paging/audit

Important constraints:
- This does NOT reuse or modify the CCTV `/api/v1/jobs` endpoints or the CCTV `jobs` table.
- All HR async work runs on the RQ queue named "hr".
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.hr.queue import get_hr_queue
from app.hr.tasks import explain_one, explain_run, run_screening
from app.models.models import (
    HROpening,
    HRResume,
    HRScreeningExplanation,
    HRScreeningResult,
    HRScreeningRun,
)


router = APIRouter(tags=["hr"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# -------------------------
# Pydantic schemas
# -------------------------


class ScreeningRunCreateRequest(BaseModel):
    """
    Optional overrides for run configuration.

    If omitted, the defaults from Settings are used.
    """

    view_types: list[str] | None = None
    k_per_view: int | None = None
    pool_size: int | None = None
    top_n: int | None = None


class ScreeningRunOut(BaseModel):
    id: UUID
    opening_id: UUID
    store_id: UUID
    status: str
    config_json: dict
    model_versions_json: dict
    rq_job_id: str | None
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    progress_total: int
    progress_done: int


class ScreeningResultRowOut(BaseModel):
    rank: int
    resume_id: UUID
    original_filename: str
    resume_status: str
    embedding_status: str
    final_score: float
    rerank_score: float | None
    retrieval_score: float | None
    best_view_type: str | None


class ScreeningResultsPageOut(BaseModel):
    run_id: UUID
    status: str
    page: int
    page_size: int
    total_results: int
    results: list[ScreeningResultRowOut]


class ScreeningExplanationOut(BaseModel):
    run_id: UUID
    resume_id: UUID
    rank: int | None
    model_name: str
    prompt_version: str
    explanation_json: dict
    created_at: datetime


class ScreeningExplainRunRequest(BaseModel):
    top_n: int | None = None
    force: bool = False


class ScreeningExplainOneRequest(BaseModel):
    force: bool = True


class ScreeningEnqueueResponse(BaseModel):
    enqueued: bool
    rq_job_id: str | None = None


def _run_out(run: HRScreeningRun) -> ScreeningRunOut:
    return ScreeningRunOut(
        id=run.id,
        opening_id=run.opening_id,
        store_id=run.store_id,
        status=run.status,
        config_json=run.config_json or {},
        model_versions_json=run.model_versions_json or {},
        rq_job_id=run.rq_job_id,
        error=run.error,
        created_at=run.created_at,
        started_at=run.started_at,
        finished_at=run.finished_at,
        progress_total=int(run.progress_total or 0),
        progress_done=int(run.progress_done or 0),
    )


def _require_run(db: Session, run_id: UUID) -> HRScreeningRun:
    run = db.get(HRScreeningRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="ScreeningRun not found")
    return run


def _require_gemini_configured() -> None:
    """
    Phase 4 requires a Gemini API key.

    We keep this as a helper so both endpoints and tasks have a consistent error message.
    """
    if not (settings.gemini_api_key or "").strip():
        raise HTTPException(
            status_code=400,
            detail="Gemini is not configured (set GEMINI_API_KEY)",
        )


# -------------------------
# Create + poll runs
# -------------------------


@router.post(
    "/openings/{opening_id}/screening-runs",
    response_model=ScreeningRunOut,
    status_code=status.HTTP_201_CREATED,
)
def create_screening_run(
    opening_id: UUID,
    body: ScreeningRunCreateRequest = Body(default_factory=ScreeningRunCreateRequest),
    db: Session = Depends(get_db),
) -> ScreeningRunOut:
    """
    Create and enqueue a ScreeningRun for an opening.

    This mirrors the "create job + enqueue" pattern used by the CCTV pipeline,
    but uses separate tables/endpoints for HR.
    """
    opening = db.get(HROpening, opening_id)
    if opening is None:
        raise HTTPException(status_code=404, detail="Opening not found")

    # Build the effective config (fill defaults from Settings).
    config_json = {
        "view_types": body.view_types or list(settings.hr_screening_default_view_types),
        "k_per_view": int(body.k_per_view or settings.hr_screening_default_k_per_view),
        "pool_size": int(body.pool_size or settings.hr_screening_default_pool_size),
        "top_n": int(body.top_n or settings.hr_screening_default_top_n),
    }

    model_versions_json = {
        "embed": settings.hr_embed_model_name,
        "embed_dim": int(settings.hr_embed_dim),
        "rerank": settings.hr_reranker_model_name,
    }

    run = HRScreeningRun(
        id=uuid4(),
        opening_id=opening.id,
        store_id=opening.store_id,
        status="QUEUED",
        config_json=config_json,
        model_versions_json=model_versions_json,
        progress_total=0,
        progress_done=0,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    try:
        job = get_hr_queue().enqueue(
            run_screening,
            str(run.id),
            job_timeout=int(settings.hr_screening_job_timeout_sec),
        )
        run.rq_job_id = job.id
        db.add(run)
        db.commit()
        db.refresh(run)
        return _run_out(run)
    except Exception as e:
        # Queue failures should not crash the API; mark run FAILED so UI can show it.
        run.status = "FAILED"
        run.error = f"queue_error: {e}"
        run.finished_at = _utcnow()
        db.add(run)
        db.commit()
        db.refresh(run)
        return _run_out(run)


@router.get("/screening-runs/{run_id}", response_model=ScreeningRunOut)
def get_screening_run(run_id: UUID, db: Session = Depends(get_db)) -> ScreeningRunOut:
    run = _require_run(db, run_id)
    return _run_out(run)


@router.post("/screening-runs/{run_id}/cancel", response_model=ScreeningRunOut)
def cancel_screening_run(run_id: UUID, db: Session = Depends(get_db)) -> ScreeningRunOut:
    """
    Cancel a ScreeningRun.

    Cancellation is best-effort:
    - If the job is already running, the worker will check DB state and stop at the next checkpoint.
    - If the job is queued, it may still start briefly and exit immediately.
    """
    run = _require_run(db, run_id)

    if run.status in {"DONE", "FAILED"}:
        return _run_out(run)

    run.status = "CANCELLED"
    run.finished_at = _utcnow()
    db.add(run)
    db.commit()
    db.refresh(run)
    return _run_out(run)


@router.post(
    "/screening-runs/{run_id}/retry",
    response_model=ScreeningRunOut,
    status_code=status.HTTP_201_CREATED,
)
def retry_screening_run(run_id: UUID, db: Session = Depends(get_db)) -> ScreeningRunOut:
    """
    Retry a ScreeningRun by creating a NEW run with the same config.

    We do this to preserve audit history (the old run remains immutable).
    """
    old = _require_run(db, run_id)
    opening = db.get(HROpening, old.opening_id)
    if opening is None:
        raise HTTPException(status_code=404, detail="Opening not found")

    new_run = HRScreeningRun(
        id=uuid4(),
        opening_id=old.opening_id,
        store_id=old.store_id,
        status="QUEUED",
        config_json=old.config_json or {},
        model_versions_json={
            "embed": settings.hr_embed_model_name,
            "embed_dim": int(settings.hr_embed_dim),
            "rerank": settings.hr_reranker_model_name,
        },
        progress_total=0,
        progress_done=0,
    )
    db.add(new_run)
    db.commit()
    db.refresh(new_run)

    try:
        job = get_hr_queue().enqueue(
            run_screening,
            str(new_run.id),
            job_timeout=int(settings.hr_screening_job_timeout_sec),
        )
        new_run.rq_job_id = job.id
        db.add(new_run)
        db.commit()
        db.refresh(new_run)
        return _run_out(new_run)
    except Exception as e:
        new_run.status = "FAILED"
        new_run.error = f"queue_error: {e}"
        new_run.finished_at = _utcnow()
        db.add(new_run)
        db.commit()
        db.refresh(new_run)
        return _run_out(new_run)


# -------------------------
# Results paging
# -------------------------


@router.get("/screening-runs/{run_id}/results", response_model=ScreeningResultsPageOut)
def list_screening_results(
    run_id: UUID,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> ScreeningResultsPageOut:
    run = _require_run(db, run_id)

    if run.status != "DONE":
        raise HTTPException(
            status_code=409,
            detail={
                "status": run.status,
                "error": run.error,
                "message": "Results are not available until the run is DONE",
            },
        )

    total = (
        db.query(HRScreeningResult.resume_id)
        .filter(HRScreeningResult.run_id == run_id)
        .count()
    )

    offset = (page - 1) * page_size
    rows = (
        db.query(HRScreeningResult, HRResume)
        .join(HRResume, HRResume.id == HRScreeningResult.resume_id)
        .filter(HRScreeningResult.run_id == run_id)
        .order_by(HRScreeningResult.rank.asc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    results: list[ScreeningResultRowOut] = []
    for res, resume in rows:
        results.append(
            ScreeningResultRowOut(
                rank=int(res.rank),
                resume_id=res.resume_id,
                original_filename=resume.original_filename,
                resume_status=resume.status,
                embedding_status=resume.embedding_status,
                final_score=float(res.final_score),
                rerank_score=float(res.rerank_score) if res.rerank_score is not None else None,
                retrieval_score=float(res.retrieval_score) if res.retrieval_score is not None else None,
                best_view_type=res.best_view_type,
            )
        )

    return ScreeningResultsPageOut(
        run_id=run.id,
        status=run.status,
        page=int(page),
        page_size=int(page_size),
        total_results=int(total),
        results=results,
    )


# -------------------------
# Phase 4: Explanations (Gemini)
# -------------------------


@router.get(
    "/screening-runs/{run_id}/results/{resume_id}/explanation",
    response_model=ScreeningExplanationOut,
)
def get_screening_explanation(
    run_id: UUID, resume_id: UUID, db: Session = Depends(get_db)
) -> ScreeningExplanationOut:
    """
    Fetch the stored explanation for one result row.

    Returns 404 if explanations haven't been generated yet for this candidate.
    """
    run = _require_run(db, run_id)
    if run.status != "DONE":
        raise HTTPException(
            status_code=409,
            detail={"status": run.status, "message": "Run is not DONE yet"},
        )

    row = (
        db.query(HRScreeningExplanation)
        .filter(
            HRScreeningExplanation.run_id == run_id,
            HRScreeningExplanation.resume_id == resume_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Explanation not found")

    return ScreeningExplanationOut(
        run_id=row.run_id,
        resume_id=row.resume_id,
        rank=row.rank,
        model_name=row.model_name,
        prompt_version=row.prompt_version,
        explanation_json=row.explanation_json,
        created_at=row.created_at,
    )


@router.post(
    "/screening-runs/{run_id}/explanations",
    response_model=ScreeningEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_run_explanations(
    run_id: UUID,
    body: ScreeningExplainRunRequest = Body(default_factory=ScreeningExplainRunRequest),
    db: Session = Depends(get_db),
) -> ScreeningEnqueueResponse:
    """
    Manually enqueue explanation generation for the top N results of a run.

    This endpoint NEVER blocks on LLM calls; it only enqueues an RQ job.
    """
    _require_gemini_configured()
    run = _require_run(db, run_id)
    if run.status != "DONE":
        raise HTTPException(
            status_code=409,
            detail={"status": run.status, "message": "Run is not DONE yet"},
        )

    top_n = int(body.top_n or settings.gemini_max_top_n)
    top_n = max(1, min(int(settings.gemini_max_top_n), top_n))

    job = get_hr_queue().enqueue(
        explain_run,
        str(run_id),
        top_n=top_n,
        force=bool(body.force),
        job_timeout=int(settings.hr_screening_job_timeout_sec),
    )
    return ScreeningEnqueueResponse(enqueued=True, rq_job_id=job.id)


@router.post(
    "/screening-runs/{run_id}/results/{resume_id}/explanation/recompute",
    response_model=ScreeningEnqueueResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_single_explanation(
    run_id: UUID,
    resume_id: UUID,
    body: ScreeningExplainOneRequest = Body(default_factory=ScreeningExplainOneRequest),
    db: Session = Depends(get_db),
) -> ScreeningEnqueueResponse:
    """
    Enqueue explanation generation for a single candidate.

    Body:
      { "force": true }  # overwrite existing explanation if present
    """
    _require_gemini_configured()
    run = _require_run(db, run_id)
    if run.status != "DONE":
        raise HTTPException(
            status_code=409,
            detail={"status": run.status, "message": "Run is not DONE yet"},
        )

    # Ensure the resume exists for this run (avoid generating explanations for unrelated resumes).
    exists = (
        db.query(HRScreeningResult.resume_id)
        .filter(HRScreeningResult.run_id == run_id, HRScreeningResult.resume_id == resume_id)
        .first()
    )
    if exists is None:
        raise HTTPException(status_code=404, detail="Resume is not part of this run")

    job = get_hr_queue().enqueue(
        explain_one,
        str(run_id),
        str(resume_id),
        force=bool(body.force),
        job_timeout=int(settings.hr_screening_job_timeout_sec),
    )
    return ScreeningEnqueueResponse(enqueued=True, rq_job_id=job.id)
