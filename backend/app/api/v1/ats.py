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

from fastapi import APIRouter, Body, Depends, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import require_permission
from app.auth.permissions import HR_RECRUITING_READ, HR_RECRUITING_WRITE
from app.core.errors import AppError
from app.core.responses import ok
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
from app.shared.types import AuthContext

router = APIRouter(tags=["hr", "ats"])

def _ok_model(model: BaseModel) -> dict[str, object]:
    return ok(model.model_dump())


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
    tenant_id: UUID
    company_id: UUID
    branch_id: UUID
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


def _require_opening(db: Session, *, ctx: AuthContext, branch_id: UUID, opening_id: UUID) -> HROpening:
    opening = (
        db.query(HROpening)
        .filter(
            HROpening.id == opening_id,
            HROpening.tenant_id == ctx.scope.tenant_id,
            HROpening.branch_id == branch_id,
        )
        .one_or_none()
    )
    if opening is None:
        raise AppError(code="hr.opening.not_found", message="Opening not found", status_code=404)
    return opening


def _require_run(db: Session, *, ctx: AuthContext, branch_id: UUID, run_id: UUID) -> HRScreeningRun:
    run = (
        db.query(HRScreeningRun)
        .filter(
            HRScreeningRun.id == run_id,
            HRScreeningRun.tenant_id == ctx.scope.tenant_id,
            HRScreeningRun.branch_id == branch_id,
        )
        .one_or_none()
    )
    if run is None:
        raise AppError(code="hr.screening_run.not_found", message="Screening run not found", status_code=404)
    return run


def _require_application(
    db: Session, *, ctx: AuthContext, branch_id: UUID, application_id: UUID
) -> HRApplication:
    app = (
        db.query(HRApplication)
        .filter(
            HRApplication.id == application_id,
            HRApplication.tenant_id == ctx.scope.tenant_id,
            HRApplication.branch_id == branch_id,
        )
        .one_or_none()
    )
    if app is None:
        raise AppError(code="ats.application.not_found", message="Application not found", status_code=404)
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
        tenant_id=app.tenant_id,
        company_id=app.company_id,
        branch_id=app.branch_id,
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


def _require_stage(
    db: Session, *, tenant_id: UUID, opening_id: UUID, stage_name: str
) -> HRPipelineStage:
    """
    Resolve a stage for an opening by name (case-insensitive).

    We return an actionable 400 if the stage doesn't exist, including the valid names.
    """

    stage = find_stage_by_name(db, opening_id, stage_name, tenant_id=tenant_id)
    if stage is None:
        raise AppError(
            code="ats.stage.invalid",
            message=f"Unknown stage_name: {stage_name!r}",
            status_code=400,
            details={"valid_stage_names": list_stage_names(db, opening_id, tenant_id=tenant_id)},
        )
    return stage


def _require_stage_id(
    db: Session, *, tenant_id: UUID, opening_id: UUID, stage_id: UUID
) -> HRPipelineStage:
    stage = (
        db.query(HRPipelineStage)
        .filter(
            HRPipelineStage.id == stage_id,
            HRPipelineStage.opening_id == opening_id,
            HRPipelineStage.tenant_id == tenant_id,
        )
        .one_or_none()
    )
    if stage is None:
        raise AppError(
            code="ats.stage.invalid",
            message="stage_id does not belong to this opening",
            status_code=400,
        )
    return stage


# -------------------------
# Pipeline stages
# -------------------------


@router.get(
    "/branches/{branch_id}/openings/{opening_id}/pipeline-stages",
)
def list_pipeline_stages(
    branch_id: UUID,
    opening_id: UUID,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    List pipeline stages for an opening (ordered by sort_order).

    This endpoint also lazily creates default stages if none exist. This avoids
    footguns when working with openings created before Phase 5 was installed.
    """

    _require_opening(db, ctx=ctx, branch_id=branch_id, opening_id=opening_id)

    ensure_default_pipeline_stages(db, opening_id, tenant_id=ctx.scope.tenant_id)
    db.commit()

    rows = (
        db.query(HRPipelineStage)
        .filter(HRPipelineStage.opening_id == opening_id, HRPipelineStage.tenant_id == ctx.scope.tenant_id)
        .order_by(HRPipelineStage.sort_order.asc(), HRPipelineStage.name.asc())
        .all()
    )
    return ok([_stage_out(s).model_dump() for s in rows])


@router.patch(
    "/branches/{branch_id}/openings/{opening_id}/pipeline-stages/{stage_id}",
)
def update_pipeline_stage(
    branch_id: UUID,
    opening_id: UUID,
    stage_id: UUID,
    body: PipelineStageUpdateRequest,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Update a pipeline stage (rename, reorder, mark terminal).

    This is optional for MVP but is useful for quickly iterating on pipelines.
    """

    _require_opening(db, ctx=ctx, branch_id=branch_id, opening_id=opening_id)
    stage = _require_stage_id(db, tenant_id=ctx.scope.tenant_id, opening_id=opening_id, stage_id=stage_id)

    if body.name is not None:
        stage.name = body.name.strip()
    if body.sort_order is not None:
        stage.sort_order = int(body.sort_order)
    if body.is_terminal is not None:
        stage.is_terminal = bool(body.is_terminal)

    db.add(stage)
    db.commit()
    db.refresh(stage)
    return _ok_model(_stage_out(stage))


# -------------------------
# Applications
# -------------------------


@router.post(
    "/branches/{branch_id}/screening-runs/{run_id}/applications",
    status_code=status.HTTP_201_CREATED,
)
def create_applications_from_run(
    branch_id: UUID,
    run_id: UUID,
    body: CreateApplicationsFromRunRequest = Body(default_factory=CreateApplicationsFromRunRequest),
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Bulk-create applications from a ScreeningRun.

    Supported modes:
    - Explicit resume_ids list
    - top_n: take the top N ranked results from the run (requires run.status == DONE)
    """

    run = _require_run(db, ctx=ctx, branch_id=branch_id, run_id=run_id)
    _require_opening(db, ctx=ctx, branch_id=branch_id, opening_id=run.opening_id)

    ensure_default_pipeline_stages(db, run.opening_id, tenant_id=ctx.scope.tenant_id)
    db.commit()

    stage_name = (body.stage_name or "Screened").strip()
    stage = _require_stage(db, tenant_id=ctx.scope.tenant_id, opening_id=run.opening_id, stage_name=stage_name)

    if body.resume_ids and body.top_n:
        raise AppError(
            code="validation_error",
            message="Provide either resume_ids or top_n (not both)",
            status_code=400,
        )
    if not body.resume_ids and body.top_n is None:
        raise AppError(code="validation_error", message="Provide resume_ids or top_n", status_code=400)

    resume_ids: list[UUID]
    if body.resume_ids:
        resume_ids = list(body.resume_ids)
        # Validate all resume_ids belong to this opening.
        found = (
            db.query(HRResume.id)
            .filter(
                HRResume.opening_id == run.opening_id,
                HRResume.tenant_id == ctx.scope.tenant_id,
                HRResume.branch_id == branch_id,
                HRResume.id.in_(resume_ids),
            )
            .all()
        )
        found_set = {r[0] for r in found}
        missing = [rid for rid in resume_ids if rid not in found_set]
        if missing:
            raise AppError(
                code="validation_error",
                message="Some resumes do not belong to this opening",
                status_code=400,
                details={"resume_ids": missing},
            )
    else:
        if run.status != "DONE":
            raise AppError(
                code="hr.screening_run.invalid_state",
                message="Run must be DONE to create applications by top_n",
                status_code=400,
                details={"status": run.status},
            )
        top_n = max(1, min(int(body.top_n or 0), 5000))
        resume_ids = [
            r[0]
            for r in (
                db.query(HRScreeningResult.resume_id)
                .filter(HRScreeningResult.run_id == run.id, HRScreeningResult.tenant_id == ctx.scope.tenant_id)
                .order_by(HRScreeningResult.rank.asc())
                .limit(top_n)
                .all()
            )
        ]

    if not resume_ids:
        return _ok_model(CreateApplicationsResponse(created_count=0, skipped_count=0, application_ids=[]))

    existing = (
        db.query(HRApplication.resume_id)
        .filter(
            HRApplication.opening_id == run.opening_id,
            HRApplication.tenant_id == ctx.scope.tenant_id,
            HRApplication.branch_id == branch_id,
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
            tenant_id=ctx.scope.tenant_id,
            company_id=run.company_id,
            branch_id=branch_id,
            resume_id=rid,
            stage_id=stage.id,
            status="ACTIVE",
            source_run_id=run.id,
        )
        db.add(app)
        created_ids.append(app_id)

    db.commit()

    return _ok_model(
        CreateApplicationsResponse(
            created_count=len(created_ids),
            skipped_count=len(resume_ids) - len(created_ids),
            application_ids=created_ids,
        )
    )


@router.post(
    "/branches/{branch_id}/openings/{opening_id}/applications",
    status_code=status.HTTP_201_CREATED,
)
def create_application(
    branch_id: UUID,
    opening_id: UUID,
    body: ApplicationCreateRequest,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Manually create an application from a resume.

    This is useful when:
    - a resume was uploaded but not part of a ScreeningRun, or
    - you want to add an applicant directly to the pipeline.
    """

    opening = _require_opening(db, ctx=ctx, branch_id=branch_id, opening_id=opening_id)

    ensure_default_pipeline_stages(db, opening_id, tenant_id=ctx.scope.tenant_id)
    db.commit()

    resume = (
        db.query(HRResume)
        .filter(
            HRResume.id == body.resume_id,
            HRResume.opening_id == opening_id,
            HRResume.tenant_id == ctx.scope.tenant_id,
            HRResume.branch_id == branch_id,
        )
        .one_or_none()
    )
    if resume is None:
        raise AppError(
            code="validation_error",
            message="resume_id does not belong to this opening",
            status_code=400,
        )

    stage_name = (body.stage_name or "Applied").strip()
    stage = _require_stage(db, tenant_id=ctx.scope.tenant_id, opening_id=opening_id, stage_name=stage_name)

    existing = (
        db.query(HRApplication)
        .filter(
            HRApplication.opening_id == opening_id,
            HRApplication.tenant_id == ctx.scope.tenant_id,
            HRApplication.branch_id == branch_id,
            HRApplication.resume_id == resume.id,
        )
        .first()
    )
    if existing is not None:
        return _ok_model(_application_out(existing, resume))

    app = HRApplication(
        id=uuid4(),
        opening_id=opening.id,
        tenant_id=opening.tenant_id,
        company_id=opening.company_id,
        branch_id=opening.branch_id,
        resume_id=resume.id,
        stage_id=stage.id,
        status="ACTIVE",
        source_run_id=None,
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return _ok_model(_application_out(app, resume))


@router.get("/branches/{branch_id}/openings/{opening_id}/applications")
def list_applications(
    branch_id: UUID,
    opening_id: UUID,
    stage_id: UUID | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    List applications for an opening (Kanban-friendly).

    Filters:
    - stage_id: show one column
    - status: ACTIVE|REJECTED|HIRED
    """

    _require_opening(db, ctx=ctx, branch_id=branch_id, opening_id=opening_id)

    q = (
        db.query(HRApplication, HRResume)
        .join(HRResume, HRResume.id == HRApplication.resume_id)
        .filter(
            HRApplication.opening_id == opening_id,
            HRApplication.tenant_id == ctx.scope.tenant_id,
            HRApplication.branch_id == branch_id,
        )
    )

    if stage_id is not None:
        q = q.filter(HRApplication.stage_id == stage_id)

    if status_filter is not None:
        q = q.filter(HRApplication.status == status_filter)

    rows = q.order_by(HRApplication.updated_at.desc(), HRApplication.created_at.desc()).all()
    return ok([_application_out(app, resume).model_dump() for app, resume in rows])


@router.patch("/branches/{branch_id}/applications/{application_id}")
def update_application(
    branch_id: UUID,
    application_id: UUID,
    body: ApplicationUpdateRequest,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    """
    Move an application to another stage (drag/drop) or update stage by name.
    """

    app = _require_application(db, ctx=ctx, branch_id=branch_id, application_id=application_id)
    opening_id = app.opening_id

    ensure_default_pipeline_stages(db, opening_id, tenant_id=ctx.scope.tenant_id)
    db.commit()

    if body.stage_id and body.stage_name:
        raise AppError(
            code="validation_error",
            message="Provide stage_id OR stage_name (not both)",
            status_code=400,
        )

    if body.stage_id is not None:
        stage = _require_stage_id(db, tenant_id=ctx.scope.tenant_id, opening_id=opening_id, stage_id=body.stage_id)
        app.stage_id = stage.id
    elif body.stage_name is not None:
        stage = _require_stage(db, tenant_id=ctx.scope.tenant_id, opening_id=opening_id, stage_name=body.stage_name)
        app.stage_id = stage.id

    db.add(app)
    db.commit()
    db.refresh(app)

    resume = (
        db.query(HRResume)
        .filter(HRResume.id == app.resume_id, HRResume.tenant_id == ctx.scope.tenant_id)
        .one_or_none()
    )
    if resume is None:
        raise AppError(
            code="ats.application.resume_missing",
            message="Resume missing for application",
            status_code=500,
        )

    return _ok_model(_application_out(app, resume))


def _set_terminal_status(
    db: Session, *, tenant_id: UUID, app: HRApplication, terminal_status: str
) -> HRApplication:
    """
    Helper for /reject and /hire.

    We update both:
    - application.status (ACTIVE|REJECTED|HIRED)
    - application.stage_id to the terminal stage if it exists ("Rejected"/"Hired")
    """

    app.status = terminal_status

    terminal_stage = find_stage_by_name(db, app.opening_id, terminal_status.title(), tenant_id=tenant_id)
    if terminal_stage is not None:
        app.stage_id = terminal_stage.id

    db.add(app)
    db.commit()
    db.refresh(app)
    return app


@router.post("/branches/{branch_id}/applications/{application_id}/reject")
def reject_application(
    branch_id: UUID,
    application_id: UUID,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    app = _require_application(db, ctx=ctx, branch_id=branch_id, application_id=application_id)
    ensure_default_pipeline_stages(db, app.opening_id, tenant_id=ctx.scope.tenant_id)
    db.commit()

    app = _set_terminal_status(db, tenant_id=ctx.scope.tenant_id, app=app, terminal_status="REJECTED")
    resume = db.query(HRResume).filter(HRResume.id == app.resume_id, HRResume.tenant_id == ctx.scope.tenant_id).one_or_none()
    if resume is None:
        raise AppError(
            code="ats.application.resume_missing",
            message="Resume missing for application",
            status_code=500,
        )
    return _ok_model(_application_out(app, resume))


@router.post("/branches/{branch_id}/applications/{application_id}/hire")
def hire_application(
    branch_id: UUID,
    application_id: UUID,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    app = _require_application(db, ctx=ctx, branch_id=branch_id, application_id=application_id)
    ensure_default_pipeline_stages(db, app.opening_id, tenant_id=ctx.scope.tenant_id)
    db.commit()

    app = _set_terminal_status(db, tenant_id=ctx.scope.tenant_id, app=app, terminal_status="HIRED")
    resume = db.query(HRResume).filter(HRResume.id == app.resume_id, HRResume.tenant_id == ctx.scope.tenant_id).one_or_none()
    if resume is None:
        raise AppError(
            code="ats.application.resume_missing",
            message="Resume missing for application",
            status_code=500,
        )
    return _ok_model(_application_out(app, resume))


# -------------------------
# Notes
# -------------------------


@router.post(
    "/branches/{branch_id}/applications/{application_id}/notes",
    status_code=status.HTTP_201_CREATED,
)
def create_note(
    branch_id: UUID,
    application_id: UUID,
    body: NoteCreateRequest,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    app = _require_application(db, ctx=ctx, branch_id=branch_id, application_id=application_id)

    note_text = (body.note or "").strip()
    if not note_text:
        raise AppError(code="validation_error", message="note is required", status_code=400)

    note = HRApplicationNote(
        tenant_id=ctx.scope.tenant_id,
        application_id=app.id,
        author_id=ctx.user_id,
        note=note_text,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return _ok_model(
        NoteOut(
            id=note.id,
            application_id=note.application_id,
            note=note.note,
            created_at=note.created_at,
        )
    )


@router.get("/branches/{branch_id}/applications/{application_id}/notes")
def list_notes(
    branch_id: UUID,
    application_id: UUID,
    ctx: AuthContext = Depends(require_permission(HR_RECRUITING_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _require_application(db, ctx=ctx, branch_id=branch_id, application_id=application_id)

    rows = (
        db.query(HRApplicationNote)
        .filter(
            HRApplicationNote.application_id == application_id,
            HRApplicationNote.tenant_id == ctx.scope.tenant_id,
        )
        .order_by(HRApplicationNote.created_at.desc())
        .all()
    )
    return ok(
        [
            NoteOut(
                id=n.id,
                application_id=n.application_id,
                note=n.note,
                created_at=n.created_at,
            ).model_dump()
            for n in rows
        ]
    )
