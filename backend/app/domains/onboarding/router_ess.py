"""
ESS onboarding v2 endpoints (Milestone 6).

Routes:
- GET  /api/v1/ess/me/onboarding
- POST /api/v1/ess/me/onboarding/tasks/{task_id}/submit-form
- POST /api/v1/ess/me/onboarding/tasks/{task_id}/upload-document
- POST /api/v1/ess/me/onboarding/tasks/{task_id}/ack
- POST /api/v1/ess/me/onboarding/bundle/{bundle_id}/submit-packet
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from app.domains.dms.policies import require_dms_file_write
from app.core.responses import ok
from app.db.session import get_db
from app.domains.onboarding.policies import (
    require_onboarding_bundle_read,
    require_onboarding_task_read,
    require_onboarding_task_submit,
)
from app.domains.onboarding.schemas import (
    EmployeeBundleOut,
    EmployeeTaskOut,
    EssOnboardingOut,
    SubmitFormIn,
    SubmitPacketOut,
)
from app.domains.onboarding.service import OnboardingTaskService
from app.domains.profile_change.policies import require_profile_change_submit
from app.shared.types import AuthContext


router = APIRouter(prefix="/ess", tags=["onboarding"])
_svc = OnboardingTaskService()


@router.get("/me/onboarding")
def get_my_onboarding(
    ctx: AuthContext = Depends(require_onboarding_bundle_read),
    _task_ctx: AuthContext = Depends(require_onboarding_task_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    bundle, tasks = _svc.get_my_onboarding(db, ctx=ctx)
    out = EssOnboardingOut(
        bundle=EmployeeBundleOut(**bundle) if bundle is not None else None,
        tasks=[EmployeeTaskOut(**t) for t in tasks],
    )
    return ok(out.model_dump())


@router.post("/me/onboarding/tasks/{task_id}/submit-form")
def submit_form_task(
    task_id: UUID,
    payload: SubmitFormIn,
    ctx: AuthContext = Depends(require_onboarding_task_submit),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.submit_form_task(db, ctx=ctx, task_id=task_id, payload=payload.payload)
    return ok(EmployeeTaskOut(**row).model_dump())


@router.post("/me/onboarding/tasks/{task_id}/upload-document")
def upload_document_task(
    task_id: UUID,
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(require_onboarding_task_submit),
    _file_ctx: AuthContext = Depends(require_dms_file_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    # We require both onboarding.task:submit and dms:file:write for this endpoint.
    # This keeps DMS access control centralized in permission vocabulary.
    _ = _file_ctx
    row = _svc.upload_document_task(db, ctx=ctx, task_id=task_id, upload_file=file)
    return ok(EmployeeTaskOut(**row).model_dump())


@router.post("/me/onboarding/tasks/{task_id}/ack")
def ack_task(
    task_id: UUID,
    ctx: AuthContext = Depends(require_onboarding_task_submit),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.ack_task(db, ctx=ctx, task_id=task_id)
    return ok(EmployeeTaskOut(**row).model_dump())


@router.post("/me/onboarding/bundle/{bundle_id}/submit-packet")
def submit_packet(
    bundle_id: UUID,
    ctx: AuthContext = Depends(require_profile_change_submit),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    out = _svc.submit_packet(db, ctx=ctx, bundle_id=bundle_id)
    return ok(SubmitPacketOut(**out).model_dump())
