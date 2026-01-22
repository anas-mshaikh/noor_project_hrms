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

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.hr.ats import ensure_default_pipeline_stages
from app.hr.queue import get_hr_queue
from app.hr.storage import build_resume_paths, safe_resolve_under_data_dir, save_upload_to_disk
from app.hr.tasks import parse_resume
from app.models.models import HROpening, HRResume, HRResumeBatch, HRResumeView, Store

router = APIRouter(tags=["hr"])


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
    store_id: UUID
    title: str
    status: str
    created_at: datetime
    updated_at: datetime


class ResumeOut(BaseModel):
    id: UUID
    opening_id: UUID
    store_id: UUID
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
        store_id=o.store_id,
        title=o.title,
        status=o.status,
        created_at=o.created_at,
        updated_at=o.updated_at,
    )


def _resume_out(r: HRResume) -> ResumeOut:
    return ResumeOut(
        id=r.id,
        opening_id=r.opening_id,
        store_id=r.store_id,
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


def _require_opening(db: Session, opening_id: UUID) -> HROpening:
    opening = db.get(HROpening, opening_id)
    if opening is None:
        raise HTTPException(status_code=404, detail="Opening not found")
    return opening


# -------------------------
# Openings
# -------------------------


@router.post(
    "/stores/{store_id}/openings",
    response_model=OpeningOut,
    status_code=status.HTTP_201_CREATED,
)
def create_opening(
    store_id: UUID, body: OpeningCreateRequest, db: Session = Depends(get_db)
) -> OpeningOut:
    store = db.get(Store, store_id)
    if store is None:
        raise HTTPException(status_code=404, detail="Store not found")

    opening = HROpening(
        store_id=store_id,
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
    ensure_default_pipeline_stages(db, opening.id)

    db.commit()
    db.refresh(opening)
    return _opening_out(opening)


@router.get("/stores/{store_id}/openings", response_model=list[OpeningOut])
def list_openings(store_id: UUID, db: Session = Depends(get_db)) -> list[OpeningOut]:
    rows = (
        db.query(HROpening)
        .filter(HROpening.store_id == store_id)
        .order_by(HROpening.created_at.desc())
        .all()
    )
    return [_opening_out(o) for o in rows]


@router.get("/openings/{opening_id}", response_model=OpeningOut)
def get_opening(opening_id: UUID, db: Session = Depends(get_db)) -> OpeningOut:
    opening = _require_opening(db, opening_id)
    return _opening_out(opening)


@router.patch("/openings/{opening_id}", response_model=OpeningOut)
def update_opening(
    opening_id: UUID, body: OpeningUpdateRequest, db: Session = Depends(get_db)
) -> OpeningOut:
    opening = _require_opening(db, opening_id)

    if body.title is not None:
        opening.title = body.title
    if body.jd_text is not None:
        opening.jd_text = body.jd_text
    if body.requirements_json is not None:
        opening.requirements_json = body.requirements_json
    if body.status is not None:
        if body.status not in {"ACTIVE", "ARCHIVED"}:
            raise HTTPException(status_code=400, detail="Invalid status")
        opening.status = body.status

    db.add(opening)
    db.commit()
    db.refresh(opening)
    return _opening_out(opening)


# -------------------------
# Resumes
# -------------------------


@router.post(
    "/openings/{opening_id}/resumes/upload",
    response_model=UploadResumesResponse,
    status_code=status.HTTP_201_CREATED,
)
def upload_resumes(
    opening_id: UUID,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
) -> UploadResumesResponse:
    """
    Upload 1..N resumes for an opening.

    Flow:
    1) Create hr_resumes rows (status=UPLOADED) and store files to disk.
    2) Commit rows so worker can see them.
    3) Enqueue RQ jobs (one per resume) to parse using Unstructured.
    """
    opening = _require_opening(db, opening_id)

    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")

    batch = HRResumeBatch(opening_id=opening.id, store_id=opening.store_id, total_count=len(files))
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
            raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

        resume = HRResume(
            id=resume_id,
            opening_id=opening.id,
            store_id=opening.store_id,
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

    return UploadResumesResponse(batch_id=batch.id, resume_ids=resume_ids)


@router.get("/openings/{opening_id}/resumes", response_model=list[ResumeOut])
def list_resumes(
    opening_id: UUID,
    status_filter: str | None = None,
    db: Session = Depends(get_db),
) -> list[ResumeOut]:
    _require_opening(db, opening_id)

    q = db.query(HRResume).filter(HRResume.opening_id == opening_id)
    if status_filter:
        q = q.filter(HRResume.status == status_filter)
    rows = q.order_by(HRResume.created_at.desc()).all()
    return [_resume_out(r) for r in rows]


@router.get(
    "/openings/{opening_id}/resumes/index-status",
    response_model=IndexStatusOut,
)
def get_opening_index_status(opening_id: UUID, db: Session = Depends(get_db)) -> IndexStatusOut:
    """
    Phase 2 debug endpoint: counts of parsing + embedding state for one opening.

    This is intentionally simple and UI-friendly so you can quickly see whether
    the background pipeline is keeping up.
    """
    _require_opening(db, opening_id)

    total = (
        db.query(HRResume.id)
        .filter(HRResume.opening_id == opening_id)
        .count()
    )
    parsed = (
        db.query(HRResume.id)
        .filter(HRResume.opening_id == opening_id, HRResume.status == "PARSED")
        .count()
    )
    parsing_failed = (
        db.query(HRResume.id)
        .filter(HRResume.opening_id == opening_id, HRResume.status == "FAILED")
        .count()
    )
    embedded = (
        db.query(HRResume.id)
        .filter(HRResume.opening_id == opening_id, HRResume.embedding_status == "EMBEDDED")
        .count()
    )
    embedding_failed = (
        db.query(HRResume.id)
        .filter(HRResume.opening_id == opening_id, HRResume.embedding_status == "FAILED")
        .count()
    )

    return IndexStatusOut(
        opening_id=opening_id,
        total_resumes=total,
        parsed_resumes=parsed,
        parsing_failed=parsing_failed,
        embedded_resumes=embedded,
        embedding_failed=embedding_failed,
    )


@router.get("/openings/{opening_id}/resumes/batch/{batch_id}/status", response_model=BatchStatusOut)
def get_batch_status(
    opening_id: UUID, batch_id: UUID, db: Session = Depends(get_db)
) -> BatchStatusOut:
    _require_opening(db, opening_id)

    batch = db.get(HRResumeBatch, batch_id)
    if batch is None or batch.opening_id != opening_id:
        raise HTTPException(status_code=404, detail="Batch not found")

    rows = (
        db.query(HRResume.status, HRResume.id)
        .filter(HRResume.batch_id == batch_id)
        .all()
    )
    counts = {"UPLOADED": 0, "PARSING": 0, "PARSED": 0, "FAILED": 0}
    for st, _rid in rows:
        counts[str(st)] = counts.get(str(st), 0) + 1

    return BatchStatusOut(
        batch_id=batch_id,
        total_count=batch.total_count,
        uploaded_count=counts.get("UPLOADED", 0),
        parsing_count=counts.get("PARSING", 0),
        parsed_count=counts.get("PARSED", 0),
        failed_count=counts.get("FAILED", 0),
    )


@router.get("/resumes/{resume_id}/views", response_model=list[ResumeViewInfoOut])
def list_resume_views(resume_id: UUID, db: Session = Depends(get_db)) -> list[ResumeViewInfoOut]:
    """
    Phase 2 debug endpoint: list which views are stored for a resume and whether
    they have embeddings.
    """
    resume = db.get(HRResume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    rows = (
        db.query(HRResumeView)
        .filter(HRResumeView.resume_id == resume_id)
        .order_by(HRResumeView.view_type.asc())
        .all()
    )
    return [
        ResumeViewInfoOut(
            id=v.id,
            view_type=v.view_type,
            text_hash=v.text_hash,
            has_embedding=v.embedding is not None,
            tokens=v.tokens,
            updated_at=v.updated_at,
        )
        for v in rows
    ]


@router.post("/openings/{opening_id}/search", response_model=list[SearchHitOut])
def search_resumes(
    opening_id: UUID, body: SearchRequest, db: Session = Depends(get_db)
) -> list[SearchHitOut]:
    """
    Phase 2 debug endpoint (MVP retrieval):
    - Embed the query using the configured HuggingFace model.
    - Search embedded "full" resume views within the opening using pgvector cosine distance.

    This is *not* a full ATS ranking pipeline; it's only for debugging retrieval quality.
    """
    if not settings.hr_search_debug_enabled:
        # Hide this endpoint in most environments (opt-in via env var).
        raise HTTPException(status_code=404, detail="Not found")

    _require_opening(db, opening_id)

    query_text = (body.query_text or "").strip()
    if not query_text:
        raise HTTPException(status_code=400, detail="query_text is required")

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
    return out


@router.get("/resumes/{resume_id}/parsed")
def get_parsed_resume(resume_id: UUID, db: Session = Depends(get_db)) -> dict[str, Any]:
    """
    Return the parsed.json artifact for debugging.

    If the resume is not parsed yet, we return 409 with status info.
    """
    resume = db.get(HRResume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")

    if resume.status != "PARSED" or not resume.parsed_path:
        raise HTTPException(
            status_code=409,
            detail={
                "status": resume.status,
                "error": resume.error,
                "message": "Resume not parsed yet",
            },
        )

    parsed_abs = safe_resolve_under_data_dir(resume.parsed_path)
    if not parsed_abs.exists():
        raise HTTPException(status_code=404, detail="Parsed artifact missing on disk")

    try:
        return json.loads(parsed_abs.read_text("utf-8"))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read parsed artifact: {e}")
