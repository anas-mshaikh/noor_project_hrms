"""
openings.py (HR module - Phase 1 + Phase 2)

This router implements a *NEW* HR module:
- Create/list/get/update store-scoped openings
- Upload resumes for an opening (local disk storage)
- Enqueue background parsing jobs using RQ + Unstructured
- List resumes and their parsing status
- Fetch parsed artifact JSON for debugging

Phase 2 additions:
- Store resume view embeddings in Postgres (pgvector) using a HuggingFace model (BGE-M3 default).
- Provide debug endpoints to inspect index status and run small semantic searches.

Important constraints:
- This does NOT reuse the existing CCTV `/api/v1/jobs` endpoints or the CCTV `jobs` table.
- All HR file paths stored in DB are relative to `settings.data_dir` for portability.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel, Field
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.auth.deps import require_permission
from app.auth.permissions import HR_RECRUITING_READ, HR_RECRUITING_WRITE
from app.core.config import settings
from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.hr.ats import ensure_default_pipeline_stages
from app.hr.queue import get_hr_queue
from app.hr.storage import build_resume_paths, safe_resolve_under_data_dir, save_upload_to_disk
from app.hr.tasks import embed_resume, parse_resume
from app.models.models import HROpening, HRResume, HRResumeBatch, HRResumeView
from app.shared.types import AuthContext

router = APIRouter(tags=["hr"])

def _ok_model(model: BaseModel) -> dict[str, object]:
    return ok(model.model_dump())


# -------------------------
# Pydantic schemas
# -------------------------


class OpeningCreateRequest(BaseModel):
    title: str
    jd_text: str
    requirements_json: dict[str, Any] = Field(default_factory=dict)


class OpeningUpdateRequest(BaseModel):
    title: str | None = None
    jd_text: str | None = None
    requirements_json: dict[str, Any] | None = None
    status: str | None = None  # ACTIVE | ARCHIVED


class OpeningOut(BaseModel):
    id: UUID
    tenant_id: UUID
    company_id: UUID
    branch_id: UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class ResumeOut(BaseModel):
    id: UUID
    opening_id: UUID
    tenant_id: UUID
    company_id: UUID
    branch_id: UUID
    batch_id: UUID | None
    original_filename: str
    status: str
    rq_job_id: str | None
    error: str | None
    embedding_status: str
    embedding_error: str | None
    embedded_at: datetime | None
    created_at: datetime
    updated_at: datetime


class UploadResumesResponse(BaseModel):
    batch_id: UUID
    resume_ids: list[UUID]


class BatchStatusOut(BaseModel):
    batch_id: UUID
    total_count: int
    uploaded_count: int
    parsing_count: int
    parsed_count: int
    failed_count: int


class EnqueueEmbeddingRequest(BaseModel):
    """
    Request payload for enqueuing Phase 2 embedding jobs.

    Why this exists:
    - Parsing and embedding are separate background steps.
    - If embeddings were disabled or failed earlier, we need a safe manual
      "retry embeddings" entrypoint to unblock Phase 3 screening runs.
    """

    # If provided, only these resumes are enqueued (must belong to the opening).
    resume_ids: list[UUID] | None = None
    # If true, enqueue even if a resume is already EMBEDDED (force regeneration).
    force: bool = False


class EnqueueEmbeddingResponse(BaseModel):
    opening_id: UUID
    enqueued: int
    skipped: int
    rq_job_ids: list[str]


class IndexStatusOut(BaseModel):
    """
    Aggregate index/embedding status for one opening (Phase 2 debug endpoint).
    """

    opening_id: UUID
    total_resumes: int
    parsed_resumes: int
    parsing_failed: int
    embedded_resumes: int
    embedding_failed: int


class ResumeViewInfoOut(BaseModel):
    """
    Metadata for one stored resume view (text_hash + embedding presence).
    """

    id: UUID
    view_type: str
    text_hash: str
    has_embedding: bool
    tokens: int | None
    updated_at: datetime


class SearchRequest(BaseModel):
    query_text: str
    top_k: int = 10


class SearchHitOut(BaseModel):
    resume_id: UUID
    original_filename: str
    cosine_distance: float
    score: float


# -------------------------
# Helpers
# -------------------------


def _opening_out(o: HROpening) -> OpeningOut:
    return OpeningOut(
        id=o.id,
        tenant_id=o.tenant_id,
        company_id=o.company_id,
        branch_id=o.branch_id,
        title=o.title,
        status=o.status,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )


def _resume_out(r: HRResume) -> ResumeOut:
    return ResumeOut(
        id=r.id,
        opening_id=r.opening_id,
        tenant_id=r.tenant_id,
        company_id=r.company_id,
        branch_id=r.branch_id,
        batch_id=r.batch_id,
        original_filename=r.original_filename,
        status=r.status,
        rq_job_id=r.rq_job_id,
        error=r.error,
        embedding_status=r.embedding_status,
        embedding_error=r.embedding_error,
        embedded_at=r.embedded_at,
        created_at=r.created_at,
        updated_at=r.updated_at,
    )


def _require_opening(db: Session, *, tenant_id: UUID, branch_id: UUID, opening_id: UUID) -> HROpening:
    opening = (
        db.query(HROpening)
        .filter(
            HROpening.id == opening_id,
            HROpening.tenant_id == tenant_id,
            HROpening.branch_id == branch_id,
        )
        .first()
    )
    if opening is None:
        raise AppError(code="hr.opening.not_found", message="Opening not found", status_code=404)
    return opening


# -------------------------
# Openings
# -------------------------


@router.post(
    "/branches/{branch_id}/openings",
    status_code=status.HTTP_201_CREATED,
)
def create_opening(
    branch_id: UUID,
    body: OpeningCreateRequest,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if ctx.scope.company_id is None:
        raise AppError(code="iam.scope.invalid_company", message="Company scope required", status_code=400)

    opening = HROpening(
        tenant_id=ctx.scope.tenant_id,
        company_id=ctx.scope.company_id,
        branch_id=branch_id,
        title=body.title,
        jd_text=body.jd_text,
        requirements_json=body.requirements_json,
        status="ACTIVE",
    )
    db.add(opening)
    # Flush so `opening.id` is available for related rows (pipeline stages).
    db.flush()

    # Phase 5 (ATS): create default pipeline stages for this opening.
    # This keeps behavior predictable and avoids requiring a separate setup step.
    ensure_default_pipeline_stages(db, opening.id, tenant_id=ctx.scope.tenant_id)

    db.commit()
    db.refresh(opening)
    return _ok_model(_opening_out(opening))


@router.get("/branches/{branch_id}/openings")
def list_openings(
    branch_id: UUID,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = (
        db.query(HROpening)
        .filter(HROpening.tenant_id == ctx.scope.tenant_id, HROpening.branch_id == branch_id)
        .order_by(HROpening.created_at.desc())
        .all()
    )
    return ok([_opening_out(o).model_dump() for o in rows])


@router.get("/branches/{branch_id}/openings/{opening_id}")
def get_opening(
    branch_id: UUID,
    opening_id: UUID,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    opening = _require_opening(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, opening_id=opening_id)
    return _ok_model(_opening_out(opening))


@router.patch("/branches/{branch_id}/openings/{opening_id}")
def update_opening(
    branch_id: UUID,
    opening_id: UUID,
    body: OpeningUpdateRequest,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    opening = _require_opening(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, opening_id=opening_id)

    if body.title is not None:
        opening.title = body.title
    if body.jd_text is not None:
        opening.jd_text = body.jd_text
    if body.requirements_json is not None:
        opening.requirements_json = body.requirements_json
    if body.status is not None:
        if body.status not in {"ACTIVE", "ARCHIVED"}:
            raise AppError(code="validation_error", message="Invalid status", status_code=400)
        opening.status = body.status

    db.add(opening)
    db.commit()
    db.refresh(opening)
    return _ok_model(_opening_out(opening))


# -------------------------
# Resumes
# -------------------------


@router.post(
    "/branches/{branch_id}/openings/{opening_id}/resumes/upload",
    status_code=status.HTTP_201_CREATED,
)
def upload_resumes(
    branch_id: UUID,
    opening_id: UUID,
    files: list[UploadFile] = File(...),
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Upload 1..N resumes for an opening.

    Flow:
    1) Create hr_resumes rows (status=UPLOADED) and store files to disk.
    2) Commit rows so worker can see them.
    3) Enqueue RQ jobs (one per resume) to parse using Unstructured.
    """
    opening = _require_opening(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, opening_id=opening_id)

    if not files:
        raise AppError(code="validation_error", message="No files uploaded", status_code=400)

    batch = HRResumeBatch(
        opening_id=opening.id,
        tenant_id=opening.tenant_id,
        company_id=opening.company_id,
        branch_id=opening.branch_id,
        total_count=len(files),
    )
    db.add(batch)

    created: list[HRResume] = []
    resume_ids: list[UUID] = []

    # First pass: save files + create DB rows.
    for f in files:
        resume_id = uuid4()
        # We store a sanitized basename for safety and to keep paths stable.
        paths = build_resume_paths(
            opening_id=opening.id,
            resume_id=resume_id,
            original_filename=f.filename or "resume",
        )

        try:
            # Persist raw upload to disk (local storage).
            save_upload_to_disk(f, paths.raw_abs)
        except Exception as e:
            raise AppError(
                code="hr.resume.upload_failed",
                message="Failed to save upload",
                status_code=500,
            ) from e

        resume = HRResume(
            id=resume_id,
            opening_id=opening.id,
            tenant_id=opening.tenant_id,
            company_id=opening.company_id,
            branch_id=opening.branch_id,
            batch_id=batch.id,
            original_filename=Path(paths.raw_rel).name,
            file_path=paths.raw_rel,
            status="UPLOADED",
        )
        db.add(resume)
        created.append(resume)
        resume_ids.append(resume_id)

    # Commit so the RQ worker can load resumes immediately.
    db.commit()

    # Second pass: enqueue parsing jobs and store rq_job_id.
    q = get_hr_queue()
    for r in created:
        job = q.enqueue(parse_resume, str(r.id))
        r.rq_job_id = job.id
        db.add(r)

    db.commit()

    return _ok_model(UploadResumesResponse(batch_id=batch.id, resume_ids=resume_ids))


@router.get("/branches/{branch_id}/openings/{opening_id}/resumes")
def list_resumes(
    branch_id: UUID,
    opening_id: UUID,
    status_filter: str | None = None,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _require_opening(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, opening_id=opening_id)

    q = db.query(HRResume).filter(
        HRResume.opening_id == opening_id,
        HRResume.tenant_id == ctx.scope.tenant_id,
        HRResume.branch_id == branch_id,
    )
    if status_filter:
        q = q.filter(HRResume.status == status_filter)
    rows = q.order_by(HRResume.created_at.desc()).all()
    return ok([_resume_out(r).model_dump() for r in rows])


@router.post(
    "/branches/{branch_id}/openings/{opening_id}/resumes/embed",
    status_code=status.HTTP_202_ACCEPTED,
)
def enqueue_opening_embeddings(
    branch_id: UUID,
    opening_id: UUID,
    body: EnqueueEmbeddingRequest,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Phase 2: enqueue embeddings for already-parsed resumes in an opening.

    Notes:
    - This endpoint never embeds inline; it only enqueues RQ jobs.
    - Resumes must be PARSED (clean text artifacts exist on disk).
    - We skip resumes that are already EMBEDDED unless `force=true`.
    """
    _require_opening(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, opening_id=opening_id)

    q = db.query(HRResume).filter(
        HRResume.opening_id == opening_id,
        HRResume.tenant_id == ctx.scope.tenant_id,
        HRResume.branch_id == branch_id,
    )
    if body.resume_ids:
        q = q.filter(HRResume.id.in_(body.resume_ids))
    rows = q.order_by(HRResume.created_at.desc()).all()

    enqueued = 0
    skipped = 0
    job_ids: list[str] = []

    hrq = get_hr_queue()

    for resume in rows:
        if resume.status != "PARSED":
            skipped += 1
            continue

        if not body.force and resume.embedding_status == "EMBEDDED":
            skipped += 1
            continue

        # Reset state so the UI reflects that embeddings are pending.
        resume.embedding_status = "PENDING"
        resume.embedding_error = None
        resume.embedded_at = None
        db.add(resume)

        job = hrq.enqueue(embed_resume, str(resume.id))
        job_ids.append(job.id)
        enqueued += 1

    db.commit()

    return _ok_model(
        EnqueueEmbeddingResponse(
            opening_id=opening_id,
            enqueued=enqueued,
            skipped=skipped,
            rq_job_ids=job_ids,
        )
    )


@router.get(
    "/branches/{branch_id}/openings/{opening_id}/resumes/index-status",
)
def get_opening_index_status(
    branch_id: UUID,
    opening_id: UUID,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Phase 2 debug endpoint: counts of parsing + embedding state for one opening.

    This is intentionally simple and UI-friendly so you can quickly see whether
    the background pipeline is keeping up.
    """
    _require_opening(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, opening_id=opening_id)

    total = (
        db.query(HRResume.id)
        .filter(HRResume.opening_id == opening_id, HRResume.tenant_id == ctx.scope.tenant_id, HRResume.branch_id == branch_id)
        .count()
    )
    parsed = (
        db.query(HRResume.id)
        .filter(HRResume.opening_id == opening_id, HRResume.status == "PARSED", HRResume.tenant_id == ctx.scope.tenant_id, HRResume.branch_id == branch_id)
        .count()
    )
    parsing_failed = (
        db.query(HRResume.id)
        .filter(HRResume.opening_id == opening_id, HRResume.status == "FAILED", HRResume.tenant_id == ctx.scope.tenant_id, HRResume.branch_id == branch_id)
        .count()
    )
    embedded = (
        db.query(HRResume.id)
        .filter(HRResume.opening_id == opening_id, HRResume.embedding_status == "EMBEDDED", HRResume.tenant_id == ctx.scope.tenant_id, HRResume.branch_id == branch_id)
        .count()
    )
    embedding_failed = (
        db.query(HRResume.id)
        .filter(HRResume.opening_id == opening_id, HRResume.embedding_status == "FAILED", HRResume.tenant_id == ctx.scope.tenant_id, HRResume.branch_id == branch_id)
        .count()
    )

    return _ok_model(
        IndexStatusOut(
            opening_id=opening_id,
            total_resumes=total,
            parsed_resumes=parsed,
            parsing_failed=parsing_failed,
            embedded_resumes=embedded,
            embedding_failed=embedding_failed,
        )
    )


@router.get("/branches/{branch_id}/openings/{opening_id}/resumes/batch/{batch_id}/status")
def get_batch_status(
    branch_id: UUID,
    opening_id: UUID,
    batch_id: UUID,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _require_opening(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, opening_id=opening_id)

    batch = (
        db.query(HRResumeBatch)
        .filter(
            HRResumeBatch.id == batch_id,
            HRResumeBatch.opening_id == opening_id,
            HRResumeBatch.tenant_id == ctx.scope.tenant_id,
            HRResumeBatch.branch_id == branch_id,
        )
        .first()
    )
    if batch is None:
        raise AppError(code="hr.resume_batch.not_found", message="Batch not found", status_code=404)

    rows = (
        db.query(HRResume.status, HRResume.id)
        .filter(
            HRResume.batch_id == batch_id,
            HRResume.tenant_id == ctx.scope.tenant_id,
            HRResume.branch_id == branch_id,
        )
        .all()
    )
    counts = {"UPLOADED": 0, "PARSING": 0, "PARSED": 0, "FAILED": 0}
    for st, _rid in rows:
        counts[str(st)] = counts.get(str(st), 0) + 1

    return _ok_model(
        BatchStatusOut(
            batch_id=batch_id,
            total_count=batch.total_count,
            uploaded_count=counts.get("UPLOADED", 0),
            parsing_count=counts.get("PARSING", 0),
            parsed_count=counts.get("PARSED", 0),
            failed_count=counts.get("FAILED", 0),
        )
    )


@router.get("/branches/{branch_id}/resumes/{resume_id}/views")
def list_resume_views(
    branch_id: UUID,
    resume_id: UUID,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Phase 2 debug endpoint: list which views are stored for a resume and whether
    they have embeddings.
    """
    resume = (
        db.query(HRResume)
        .filter(
            HRResume.id == resume_id,
            HRResume.tenant_id == ctx.scope.tenant_id,
            HRResume.branch_id == branch_id,
        )
        .first()
    )
    if resume is None:
        raise AppError(code="hr.resume.not_found", message="Resume not found", status_code=404)

    rows = (
        db.query(HRResumeView)
        .filter(
            HRResumeView.resume_id == resume_id,
            HRResumeView.tenant_id == ctx.scope.tenant_id,
        )
        .order_by(HRResumeView.view_type.asc())
        .all()
    )
    return ok(
        [
            ResumeViewInfoOut(
                id=v.id,
                view_type=v.view_type,
                text_hash=v.text_hash,
                has_embedding=v.embedding is not None,
                tokens=v.tokens,
                updated_at=v.updated_at,
            ).model_dump()
            for v in rows
        ]
    )


@router.post("/branches/{branch_id}/openings/{opening_id}/search")
def search_resumes(
    branch_id: UUID,
    opening_id: UUID,
    body: SearchRequest,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Phase 2 debug endpoint (MVP retrieval):
    - Embed the query using the configured HuggingFace model.
    - Search embedded "full" resume views within the opening using pgvector cosine distance.

    This is *not* a full ATS ranking pipeline; it's only for debugging retrieval quality.
    """
    if not settings.hr_search_debug_enabled:
        # Hide this endpoint in most environments (opt-in via env var).
        raise AppError(code="hr.search.not_found", message="Not found", status_code=404)

    _require_opening(db, tenant_id=ctx.scope.tenant_id, branch_id=branch_id, opening_id=opening_id)

    query_text = (body.query_text or "").strip()
    if not query_text:
        raise AppError(code="validation_error", message="query_text is required", status_code=400)

    top_k = max(1, min(int(body.top_k), 50))

    # Embed query (normalized embedding => cosine_distance works well).
    from app.hr.embeddings import embed_text

    q_emb = embed_text(query_text)
    dist_expr = HRResumeView.embedding.cosine_distance(q_emb)

    rows = (
        db.query(HRResume, dist_expr.label("distance"))
        .join(HRResumeView, HRResumeView.resume_id == HRResume.id)
        .filter(
            HRResume.opening_id == opening_id,
            HRResumeView.view_type == "full",
            HRResumeView.embedding.isnot(None),
            HRResumeView.tenant_id == ctx.scope.tenant_id,
        )
        .order_by(dist_expr.asc())
        .limit(top_k)
        .all()
    )

    out: list[SearchHitOut] = []
    for resume, dist in rows:
        dist_f = float(dist)
        out.append(
            SearchHitOut(
                resume_id=resume.id,
                original_filename=resume.original_filename,
                cosine_distance=dist_f,
                score=max(0.0, 1.0 - dist_f),
            )
        )
    return ok([x.model_dump() for x in out])


@router.get("/branches/{branch_id}/resumes/{resume_id}/parsed")
def get_parsed_resume(
    branch_id: UUID,
    resume_id: UUID,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Return the parsed.json artifact for debugging.

    If the resume is not parsed yet, we return 409 with status info.
    """
    resume = (
        db.query(HRResume)
        .filter(
            HRResume.id == resume_id,
            HRResume.tenant_id == ctx.scope.tenant_id,
            HRResume.branch_id == branch_id,
        )
        .first()
    )
    if resume is None:
        raise AppError(code="hr.resume.not_found", message="Resume not found", status_code=404)

    if resume.status != "PARSED" or not resume.parsed_path:
        raise AppError(
            code="hr.resume.not_parsed",
            message="Resume not parsed yet",
            status_code=409,
            details={"status": resume.status, "error": resume.error},
        )

    parsed_abs = safe_resolve_under_data_dir(resume.parsed_path)
    if not parsed_abs.exists():
        raise AppError(
            code="hr.resume.parsed_artifact_missing",
            message="Parsed artifact missing on disk",
            status_code=404,
        )

    try:
        return ok(json.loads(parsed_abs.read_text("utf-8")))
    except Exception as e:
        raise AppError(
            code="hr.resume.parsed_artifact_read_failed",
            message="Failed to read parsed artifact",
            status_code=500,
        ) from e
