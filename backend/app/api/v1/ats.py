"""
ats.py (HR module - Phase 5)

This router implements an MVP Applicant Tracking System (ATS) layer on top of:
- Openings (Phase 1)
- Resumes (Phase 1)
- ScreeningRun results (Phase 3)

MVP decision:
- We do NOT introduce a canonical "candidate" identity yet.
- Each resume is treated as the applicant (1 resume = 1 application).

Important constraints:
- This does NOT reuse or modify the CCTV `/api/v1/jobs` endpoints or the CCTV `jobs` table.
- ATS is CRUD-only in Phase 5 (no new RQ jobs).
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID, uuid4

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.hr.ats import ensure_default_pipeline_stages, find_stage_by_name, list_stage_names
from app.models.models import (
    HRApplication,
    HRApplicationNote,
    HROpening,
    HRPipelineStage,
    HRResume,
    HRScreeningResult,
    HRScreeningRun,
)

router = APIRouter(tags=["hr", "ats"])


# -------------------------
# Pydantic schemas
# -------------------------


class PipelineStageOut(BaseModel):
    id: UUID
    opening_id: UUID
    name: str
    sort_order: int
    is_terminal: bool
    created_at: datetime


class PipelineStageUpdateRequest(BaseModel):
    name: str | None = None
    sort_order: int | None = None
    is_terminal: bool | None = None


class ResumeMetaOut(BaseModel):
    id: UUID
    original_filename: str
    status: str
    error: str | None


class ApplicationOut(BaseModel):
    id: UUID
    opening_id: UUID
    store_id: UUID
    resume_id: UUID
    stage_id: UUID | None
    status: str
    source_run_id: UUID | None
    created_at: datetime
    updated_at: datetime
    resume: ResumeMetaOut


class CreateApplicationsFromRunRequest(BaseModel):
    resume_ids: list[UUID] | None = None
    top_n: int | None = None
    stage_name: str | None = None


class CreateApplicationsResponse(BaseModel):
    created_count: int
    skipped_count: int
    application_ids: list[UUID]


class ApplicationCreateRequest(BaseModel):
    resume_id: UUID
    stage_name: str | None = None


class ApplicationUpdateRequest(BaseModel):
    stage_id: UUID | None = None
    stage_name: str | None = None


class NoteCreateRequest(BaseModel):
    note: str


class NoteOut(BaseModel):
    id: UUID
    application_id: UUID
    note: str
    created_at: datetime


# -------------------------
# Helpers
# -------------------------


def _require_opening(db: Session, opening_id: UUID) -> HROpening:
    opening = db.get(HROpening, opening_id)
    if opening is None:
        raise HTTPException(status_code=404, detail="Opening not found")
    return opening


def _require_run(db: Session, run_id: UUID) -> HRScreeningRun:
    run = db.get(HRScreeningRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="ScreeningRun not found")
    return run


def _require_application(db: Session, application_id: UUID) -> HRApplication:
    app = db.get(HRApplication, application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


def _stage_out(s: HRPipelineStage) -> PipelineStageOut:
    return PipelineStageOut(
        id=s.id,
        opening_id=s.opening_id,
        name=s.name,
        sort_order=int(s.sort_order),
        is_terminal=bool(s.is_terminal),
        created_at=s.created_at,
    )


def _application_out(app: HRApplication, resume: HRResume) -> ApplicationOut:
    return ApplicationOut(
        id=app.id,
        opening_id=app.opening_id,
        store_id=app.store_id,
        resume_id=app.resume_id,
        stage_id=app.stage_id,
        status=app.status,
        source_run_id=app.source_run_id,
        created_at=app.created_at,
        updated_at=app.updated_at,
        resume=ResumeMetaOut(
            id=resume.id,
            original_filename=resume.original_filename,
            status=resume.status,
            error=resume.error,
        ),
    )


def _require_stage(db: Session, opening_id: UUID, stage_name: str) -> HRPipelineStage:
    """
    Resolve a stage for an opening by name (case-insensitive).

    We return an actionable 400 if the stage doesn't exist, including the valid names.
    """

    stage = find_stage_by_name(db, opening_id, stage_name)
    if stage is None:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Unknown stage_name: {stage_name!r}",
                "valid_stage_names": list_stage_names(db, opening_id),
            },
        )
    return stage


def _require_stage_id(db: Session, opening_id: UUID, stage_id: UUID) -> HRPipelineStage:
    stage = db.get(HRPipelineStage, stage_id)
    if stage is None or stage.opening_id != opening_id:
        raise HTTPException(
            status_code=400,
            detail="stage_id does not belong to this opening",
        )
    return stage


# -------------------------
# Pipeline stages
# -------------------------


@router.get("/openings/{opening_id}/pipeline-stages", response_model=list[PipelineStageOut])
def list_pipeline_stages(opening_id: UUID, db: Session = Depends(get_db)) -> list[PipelineStageOut]:
    """
    List pipeline stages for an opening (ordered by sort_order).

    This endpoint also lazily creates default stages if none exist. This avoids
    footguns when working with openings created before Phase 5 was installed.
    """

    _require_opening(db, opening_id)

    ensure_default_pipeline_stages(db, opening_id)
    db.commit()

    rows = (
        db.query(HRPipelineStage)
        .filter(HRPipelineStage.opening_id == opening_id)
        .order_by(HRPipelineStage.sort_order.asc(), HRPipelineStage.name.asc())
        .all()
    )
    return [_stage_out(s) for s in rows]


@router.patch(
    "/openings/{opening_id}/pipeline-stages/{stage_id}",
    response_model=PipelineStageOut,
)
def update_pipeline_stage(
    opening_id: UUID,
    stage_id: UUID,
    body: PipelineStageUpdateRequest,
    db: Session = Depends(get_db),
) -> PipelineStageOut:
    """
    Update a pipeline stage (rename, reorder, mark terminal).

    This is optional for MVP but is useful for quickly iterating on pipelines.
    """

    _require_opening(db, opening_id)
    stage = _require_stage_id(db, opening_id, stage_id)

    if body.name is not None:
        stage.name = body.name.strip()
    if body.sort_order is not None:
        stage.sort_order = int(body.sort_order)
    if body.is_terminal is not None:
        stage.is_terminal = bool(body.is_terminal)

    db.add(stage)
    db.commit()
    db.refresh(stage)
    return _stage_out(stage)


# -------------------------
# Applications
# -------------------------


@router.post(
    "/screening-runs/{run_id}/applications",
    response_model=CreateApplicationsResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_applications_from_run(
    run_id: UUID,
    body: CreateApplicationsFromRunRequest = Body(default_factory=CreateApplicationsFromRunRequest),
    db: Session = Depends(get_db),
) -> CreateApplicationsResponse:
    """
    Bulk-create applications from a ScreeningRun.

    Supported modes:
    - Explicit resume_ids list
    - top_n: take the top N ranked results from the run (requires run.status == DONE)
    """

    run = _require_run(db, run_id)
    _require_opening(db, run.opening_id)

    ensure_default_pipeline_stages(db, run.opening_id)
    db.commit()

    stage_name = (body.stage_name or "Screened").strip()
    stage = _require_stage(db, run.opening_id, stage_name)

    if body.resume_ids and body.top_n:
        raise HTTPException(
            status_code=400,
            detail="Provide either resume_ids or top_n (not both)",
        )
    if not body.resume_ids and body.top_n is None:
        raise HTTPException(
            status_code=400,
            detail="Provide resume_ids or top_n",
        )

    resume_ids: list[UUID]
    if body.resume_ids:
        resume_ids = list(body.resume_ids)
        # Validate all resume_ids belong to this opening.
        found = (
            db.query(HRResume.id)
            .filter(HRResume.opening_id == run.opening_id, HRResume.id.in_(resume_ids))
            .all()
        )
        found_set = {r[0] for r in found}
        missing = [rid for rid in resume_ids if rid not in found_set]
        if missing:
            raise HTTPException(
                status_code=400,
                detail={"message": "Some resumes do not belong to this opening", "resume_ids": missing},
            )
    else:
        if run.status != "DONE":
            raise HTTPException(
                status_code=400,
                detail="Run must be DONE to create applications by top_n",
            )
        top_n = max(1, min(int(body.top_n or 0), 5000))
        resume_ids = [
            r[0]
            for r in (
                db.query(HRScreeningResult.resume_id)
                .filter(HRScreeningResult.run_id == run.id)
                .order_by(HRScreeningResult.rank.asc())
                .limit(top_n)
                .all()
            )
        ]

    if not resume_ids:
        return CreateApplicationsResponse(created_count=0, skipped_count=0, application_ids=[])

    existing = (
        db.query(HRApplication.resume_id)
        .filter(
            HRApplication.opening_id == run.opening_id,
            HRApplication.resume_id.in_(resume_ids),
        )
        .all()
    )
    existing_ids = {r[0] for r in existing}

    to_create = [rid for rid in resume_ids if rid not in existing_ids]
    created_ids: list[UUID] = []

    for rid in to_create:
        app_id = uuid4()
        app = HRApplication(
            id=app_id,
            opening_id=run.opening_id,
            store_id=run.store_id,
            resume_id=rid,
            stage_id=stage.id,
            status="ACTIVE",
            source_run_id=run.id,
        )
        db.add(app)
        created_ids.append(app_id)

    db.commit()

    return CreateApplicationsResponse(
        created_count=len(created_ids),
        skipped_count=len(resume_ids) - len(created_ids),
        application_ids=created_ids,
    )


@router.post(
    "/openings/{opening_id}/applications",
    response_model=ApplicationOut,
    status_code=status.HTTP_201_CREATED,
)
def create_application(
    opening_id: UUID,
    body: ApplicationCreateRequest,
    db: Session = Depends(get_db),
) -> ApplicationOut:
    """
    Manually create an application from a resume.

    This is useful when:
    - a resume was uploaded but not part of a ScreeningRun, or
    - you want to add an applicant directly to the pipeline.
    """

    opening = _require_opening(db, opening_id)

    ensure_default_pipeline_stages(db, opening_id)
    db.commit()

    resume = db.get(HRResume, body.resume_id)
    if resume is None or resume.opening_id != opening_id:
        raise HTTPException(status_code=400, detail="resume_id does not belong to this opening")

    stage_name = (body.stage_name or "Applied").strip()
    stage = _require_stage(db, opening_id, stage_name)

    existing = (
        db.query(HRApplication)
        .filter(HRApplication.opening_id == opening_id, HRApplication.resume_id == resume.id)
        .first()
    )
    if existing is not None:
        return _application_out(existing, resume)

    app = HRApplication(
        id=uuid4(),
        opening_id=opening.id,
        store_id=opening.store_id,
        resume_id=resume.id,
        stage_id=stage.id,
        status="ACTIVE",
        source_run_id=None,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return _application_out(app, resume)


@router.get("/openings/{opening_id}/applications", response_model=list[ApplicationOut])
def list_applications(
    opening_id: UUID,
    stage_id: UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> list[ApplicationOut]:
    """
    List applications for an opening (Kanban-friendly).

    Filters:
    - stage_id: show one column
    - status: ACTIVE|REJECTED|HIRED
    """

    _require_opening(db, opening_id)

    q = (
        db.query(HRApplication, HRResume)
        .join(HRResume, HRResume.id == HRApplication.resume_id)
        .filter(HRApplication.opening_id == opening_id)
    )

    if stage_id is not None:
        q = q.filter(HRApplication.stage_id == stage_id)

    if status_filter is not None:
        q = q.filter(HRApplication.status == status_filter)

    rows = q.order_by(HRApplication.updated_at.desc(), HRApplication.created_at.desc()).all()
    return [_application_out(app, resume) for app, resume in rows]


@router.patch("/applications/{application_id}", response_model=ApplicationOut)
def update_application(
    application_id: UUID,
    body: ApplicationUpdateRequest,
    db: Session = Depends(get_db),
) -> ApplicationOut:
    """
    Move an application to another stage (drag/drop) or update stage by name.
    """

    app = _require_application(db, application_id)
    opening_id = app.opening_id

    ensure_default_pipeline_stages(db, opening_id)
    db.commit()

    if body.stage_id and body.stage_name:
        raise HTTPException(status_code=400, detail="Provide stage_id OR stage_name (not both)")

    if body.stage_id is not None:
        stage = _require_stage_id(db, opening_id, body.stage_id)
        app.stage_id = stage.id
    elif body.stage_name is not None:
        stage = _require_stage(db, opening_id, body.stage_name)
        app.stage_id = stage.id

    db.add(app)
    db.commit()
    db.refresh(app)

    resume = db.get(HRResume, app.resume_id)
    if resume is None:
        raise HTTPException(status_code=500, detail="Resume missing for application")

    return _application_out(app, resume)


def _set_terminal_status(
    db: Session, app: HRApplication, terminal_status: str
) -> HRApplication:
    """
    Helper for /reject and /hire.

    We update both:
    - application.status (ACTIVE|REJECTED|HIRED)
    - application.stage_id to the terminal stage if it exists ("Rejected"/"Hired")
    """

    app.status = terminal_status

    terminal_stage = find_stage_by_name(db, app.opening_id, terminal_status.title())
    if terminal_stage is not None:
        app.stage_id = terminal_stage.id

    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.post("/applications/{application_id}/reject", response_model=ApplicationOut)
def reject_application(application_id: UUID, db: Session = Depends(get_db)) -> ApplicationOut:
    app = _require_application(db, application_id)
    ensure_default_pipeline_stages(db, app.opening_id)
    db.commit()

    app = _set_terminal_status(db, app, "REJECTED")
    resume = db.get(HRResume, app.resume_id)
    if resume is None:
        raise HTTPException(status_code=500, detail="Resume missing for application")
    return _application_out(app, resume)


@router.post("/applications/{application_id}/hire", response_model=ApplicationOut)
def hire_application(application_id: UUID, db: Session = Depends(get_db)) -> ApplicationOut:
    app = _require_application(db, application_id)
    ensure_default_pipeline_stages(db, app.opening_id)
    db.commit()

    app = _set_terminal_status(db, app, "HIRED")
    resume = db.get(HRResume, app.resume_id)
    if resume is None:
        raise HTTPException(status_code=500, detail="Resume missing for application")
    return _application_out(app, resume)


# -------------------------
# Notes
# -------------------------


@router.post(
    "/applications/{application_id}/notes",
    response_model=NoteOut,
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    application_id: UUID,
    body: NoteCreateRequest,
    db: Session = Depends(get_db),
) -> NoteOut:
    app = _require_application(db, application_id)

    note_text = (body.note or "").strip()
    if not note_text:
        raise HTTPException(status_code=400, detail="note is required")

    note = HRApplicationNote(application_id=app.id, author_id=None, note=note_text)
    db.add(note)
    db.commit()
    db.refresh(note)
    return NoteOut(
        id=note.id,
        application_id=note.application_id,
        note=note.note,
        created_at=note.created_at,
    )


@router.get("/applications/{application_id}/notes", response_model=list[NoteOut])
def list_notes(application_id: UUID, db: Session = Depends(get_db)) -> list[NoteOut]:
    _require_application(db, application_id)

    rows = (
        db.query(HRApplicationNote)
        .filter(HRApplicationNote.application_id == application_id)
        .order_by(HRApplicationNote.created_at.desc())
        .all()
    )
    return [
        NoteOut(
            id=n.id,
            application_id=n.application_id,
            note=n.note,
            created_at=n.created_at,
        )
        for n in rows
    ]
