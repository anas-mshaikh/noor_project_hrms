"""
onboarding.py (HR module - Phase 6)

Onboarding MVP:
- Convert a HIRED ATS application into a canonical `employees` row.
- Create an onboarding plan with default checklist tasks.
- Allow uploading/verifying onboarding documents stored locally under `settings.data_dir`.

Important constraints:
- This does NOT touch CCTV `/api/v1/jobs` endpoints or the CCTV `jobs` table.
- Employee creation MUST reuse the same service logic as the existing employees endpoint.
- All file paths stored in DB are relative to `settings.data_dir`.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.employees.schemas import EmployeeCreateRequest
from app.employees.service import create_employee_in_db
from app.hr.onboarding_defaults import insert_default_onboarding_tasks
from app.hr.onboarding_storage import build_onboarding_document_paths
from app.hr.storage import safe_resolve_under_data_dir, save_upload_to_disk
from app.models.models import (
    Employee,
    HRApplication,
    HREmployeeDocument,
    HROnboardingPlan,
    HROnboardingTask,
)

router = APIRouter(tags=["hr", "onboarding"])


# -------------------------
# Pydantic schemas
# -------------------------


class ConvertToEmployeeRequest(BaseModel):
    """
    Convert an ATS application into an Employee + onboarding plan.

    `employee` reuses the same request schema used by POST /stores/{store_id}/employees.
    """

    employee: EmployeeCreateRequest
    start_date: date | None = None


class ConvertToEmployeeResponse(BaseModel):
    employee_id: UUID
    onboarding_plan_id: UUID
    application_id: UUID


class OnboardingPlanOut(BaseModel):
    id: UUID
    store_id: UUID
    employee_id: UUID
    application_id: UUID | None
    status: str
    start_date: date | None
    created_at: datetime
    updated_at: datetime


class OnboardingTaskOut(BaseModel):
    id: UUID
    plan_id: UUID
    title: str
    task_type: str
    status: str
    sort_order: int
    due_date: date | None
    completed_at: datetime | None
    metadata_json: dict
    created_at: datetime
    updated_at: datetime


class EmployeeDocumentOut(BaseModel):
    id: UUID
    plan_id: UUID
    employee_id: UUID
    doc_type: str
    original_filename: str
    status: str
    created_at: datetime
    verified_at: datetime | None


class OnboardingBundleOut(BaseModel):
    plan: OnboardingPlanOut
    tasks: list[OnboardingTaskOut]
    documents: list[EmployeeDocumentOut]


class OnboardingTaskUpdateRequest(BaseModel):
    status: str
    due_date: date | None = None


# -------------------------
# Helpers
# -------------------------


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _require_application(db: Session, application_id: UUID) -> HRApplication:
    app = db.get(HRApplication, application_id)
    if app is None:
        raise HTTPException(status_code=404, detail="Application not found")
    return app


def _require_employee(db: Session, employee_id: UUID) -> Employee:
    emp = db.get(Employee, employee_id)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    return emp


def _plan_out(p: HROnboardingPlan) -> OnboardingPlanOut:
    return OnboardingPlanOut(
        id=p.id,
        store_id=p.store_id,
        employee_id=p.employee_id,
        application_id=p.application_id,
        status=p.status,
        start_date=p.start_date,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


def _task_out(t: HROnboardingTask) -> OnboardingTaskOut:
    return OnboardingTaskOut(
        id=t.id,
        plan_id=t.plan_id,
        title=t.title,
        task_type=t.task_type,
        status=t.status,
        sort_order=int(t.sort_order),
        due_date=t.due_date,
        completed_at=t.completed_at,
        metadata_json=t.metadata_json or {},
        created_at=t.created_at,
        updated_at=t.updated_at,
    )


def _doc_out(d: HREmployeeDocument) -> EmployeeDocumentOut:
    return EmployeeDocumentOut(
        id=d.id,
        plan_id=d.plan_id,
        employee_id=d.employee_id,
        doc_type=d.doc_type,
        original_filename=d.original_filename,
        status=d.status,
        created_at=d.created_at,
        verified_at=d.verified_at,
    )


def _find_or_create_plan_for_application(
    db: Session, *, application: HRApplication, employee_id: UUID, start_date: date | None
) -> HROnboardingPlan:
    """
    Idempotency helper:
    - If a plan already exists for this application, return it.
    - Otherwise create a plan + default tasks.
    """

    existing = (
        db.query(HROnboardingPlan)
        .filter(HROnboardingPlan.application_id == application.id)
        .order_by(HROnboardingPlan.created_at.desc())
        .first()
    )
    if existing is not None:
        return existing

    plan = HROnboardingPlan(
        store_id=application.store_id,
        employee_id=employee_id,
        application_id=application.id,
        status="ACTIVE",
        start_date=start_date,
    )
    db.add(plan)
    db.flush()  # allocate PK so tasks can reference plan_id

    insert_default_onboarding_tasks(db, plan_id=plan.id)
    return plan


# -------------------------
# API endpoints
# -------------------------


@router.post(
    "/applications/{application_id}/convert-to-employee",
    response_model=ConvertToEmployeeResponse,
    status_code=status.HTTP_201_CREATED,
)
def convert_application_to_employee(
    application_id: UUID, body: ConvertToEmployeeRequest, db: Session = Depends(get_db)
) -> ConvertToEmployeeResponse:
    """
    Convert a HIRED application into:
    - an `employees` row (canonical identity used by the attendance/face system), and
    - an onboarding plan + default tasks.

    Attendance-first constraint:
    - We keep this operation atomic: either everything is created/linked, or nothing is.

    Idempotency:
    - If the application is already linked to an employee, we reuse that employee and
      ensure an onboarding plan exists.
    """

    app = _require_application(db, application_id)
    if app.status != "HIRED":
        raise HTTPException(status_code=400, detail="Application must be HIRED to convert")

    start_date = body.start_date or app.start_date

    # If already converted, do not create a second Employee.
    if app.employee_id is not None:
        emp = _require_employee(db, app.employee_id)
        plan = _find_or_create_plan_for_application(
            db, application=app, employee_id=emp.id, start_date=start_date
        )

        # If application fields weren't populated previously, fill them in.
        if app.hired_at is None:
            app.hired_at = _now_utc()
        if app.start_date is None and start_date is not None:
            app.start_date = start_date

        db.add(app)
        db.commit()
        return ConvertToEmployeeResponse(
            employee_id=emp.id, onboarding_plan_id=plan.id, application_id=app.id
        )

    # Create the Employee inside the same transaction (reuses shared employee service).
    try:
        emp = create_employee_in_db(db, store_id=app.store_id, body=body.employee)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="employee_code already exists for this store",
        )

    # Link application -> employee and create onboarding plan.
    app.employee_id = emp.id
    app.hired_at = _now_utc()
    app.start_date = start_date
    db.add(app)

    plan = _find_or_create_plan_for_application(
        db, application=app, employee_id=emp.id, start_date=start_date
    )

    db.commit()
    return ConvertToEmployeeResponse(
        employee_id=emp.id, onboarding_plan_id=plan.id, application_id=app.id
    )


@router.get(
    "/employees/{employee_id}/onboarding",
    response_model=OnboardingBundleOut,
)
def get_employee_onboarding(employee_id: UUID, db: Session = Depends(get_db)) -> OnboardingBundleOut:
    """
    Fetch the onboarding bundle for an employee (plan + tasks + documents).

    For MVP we return the most recent ACTIVE plan; if none are ACTIVE, we return the
    most recently created plan.
    """

    _require_employee(db, employee_id)

    plan = (
        db.query(HROnboardingPlan)
        .filter(HROnboardingPlan.employee_id == employee_id, HROnboardingPlan.status == "ACTIVE")
        .order_by(HROnboardingPlan.created_at.desc())
        .first()
    )
    if plan is None:
        plan = (
            db.query(HROnboardingPlan)
            .filter(HROnboardingPlan.employee_id == employee_id)
            .order_by(HROnboardingPlan.created_at.desc())
            .first()
        )
    if plan is None:
        raise HTTPException(status_code=404, detail="No onboarding plan found for employee")

    tasks = (
        db.query(HROnboardingTask)
        .filter(HROnboardingTask.plan_id == plan.id)
        .order_by(HROnboardingTask.sort_order.asc(), HROnboardingTask.created_at.asc())
        .all()
    )
    docs = (
        db.query(HREmployeeDocument)
        .filter(HREmployeeDocument.plan_id == plan.id)
        .order_by(HREmployeeDocument.created_at.desc())
        .all()
    )

    return OnboardingBundleOut(
        plan=_plan_out(plan),
        tasks=[_task_out(t) for t in tasks],
        documents=[_doc_out(d) for d in docs],
    )


@router.patch("/onboarding/tasks/{task_id}", response_model=OnboardingTaskOut)
def update_onboarding_task(
    task_id: UUID, body: OnboardingTaskUpdateRequest, db: Session = Depends(get_db)
) -> OnboardingTaskOut:
    """
    Update an onboarding task (status, due_date).

    Status transitions:
    - DONE sets completed_at=now
    - non-DONE clears completed_at (so the UI can "undo" tasks)
    """

    task = db.get(HROnboardingTask, task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Onboarding task not found")

    status_norm = (body.status or "").strip().upper()
    if status_norm not in {"PENDING", "DONE", "BLOCKED"}:
        raise HTTPException(status_code=400, detail="Invalid status")

    task.status = status_norm
    task.due_date = body.due_date
    if status_norm == "DONE":
        task.completed_at = task.completed_at or _now_utc()
    else:
        task.completed_at = None

    db.add(task)
    db.commit()
    db.refresh(task)
    return _task_out(task)


@router.post(
    "/onboarding/plans/{plan_id}/documents/upload",
    response_model=EmployeeDocumentOut,
    status_code=status.HTTP_201_CREATED,
)
def upload_onboarding_document(
    plan_id: UUID,
    doc_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> EmployeeDocumentOut:
    """
    Upload a local onboarding document and track it in Postgres.

    The file is stored under:
      hr/onboarding/{employee_id}/{document_id}/files/{filename}

    MVP convenience:
    - If there's a matching DOCUMENT task with metadata_json.doc_type == doc_type,
      we auto-mark that task DONE.
    """

    plan = db.get(HROnboardingPlan, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Onboarding plan not found")

    doc_type_norm = (doc_type or "").strip().upper()
    if not doc_type_norm:
        raise HTTPException(status_code=400, detail="doc_type is required")
    if len(doc_type_norm) > 32:
        raise HTTPException(status_code=400, detail="doc_type is too long")

    doc_id = uuid4()
    paths = build_onboarding_document_paths(
        employee_id=plan.employee_id,
        document_id=doc_id,
        original_filename=file.filename or "document",
    )

    try:
        save_upload_to_disk(file, paths.file_abs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save upload: {e}")

    doc_row = HREmployeeDocument(
        id=doc_id,
        plan_id=plan.id,
        employee_id=plan.employee_id,
        doc_type=doc_type_norm,
        # Store the sanitized basename for UI; the raw client filename isn't trusted.
        original_filename=Path(paths.file_rel).name,
        file_path=paths.file_rel,
        status="UPLOADED",
    )
    db.add(doc_row)

    # Auto-complete matching document tasks.
    now = _now_utc()
    tasks = (
        db.query(HROnboardingTask)
        .filter(HROnboardingTask.plan_id == plan.id, HROnboardingTask.task_type == "DOCUMENT")
        .all()
    )
    for t in tasks:
        meta_doc_type = str((t.metadata_json or {}).get("doc_type") or "").strip().upper()
        if meta_doc_type == doc_type_norm and t.status != "DONE":
            t.status = "DONE"
            t.completed_at = now
            db.add(t)

    db.commit()
    db.refresh(doc_row)
    return _doc_out(doc_row)


@router.post("/onboarding/documents/{document_id}/verify", response_model=EmployeeDocumentOut)
def verify_onboarding_document(document_id: UUID, db: Session = Depends(get_db)) -> EmployeeDocumentOut:
    doc = db.get(HREmployeeDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = "VERIFIED"
    doc.verified_at = _now_utc()
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _doc_out(doc)


@router.post("/onboarding/documents/{document_id}/reject", response_model=EmployeeDocumentOut)
def reject_onboarding_document(document_id: UUID, db: Session = Depends(get_db)) -> EmployeeDocumentOut:
    doc = db.get(HREmployeeDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    doc.status = "REJECTED"
    doc.verified_at = _now_utc()
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _doc_out(doc)


@router.get("/onboarding/documents/{document_id}/download")
def download_onboarding_document(document_id: UUID, db: Session = Depends(get_db)) -> FileResponse:
    """
    Download an onboarding document stored on local disk.

    Security:
    - file_path is resolved under `settings.data_dir` using `safe_resolve_under_data_dir`
      to prevent directory traversal.
    """

    doc = db.get(HREmployeeDocument, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")

    abs_path = safe_resolve_under_data_dir(doc.file_path)
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="File missing on disk")

    return FileResponse(
        path=str(abs_path),
        filename=doc.original_filename or abs_path.name,
        media_type="application/octet-stream",
    )

