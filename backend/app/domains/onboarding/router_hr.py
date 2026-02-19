"""
HR/admin onboarding v2 endpoints (Milestone 6).

Routes:
- GET  /api/v1/onboarding/plan-templates
- POST /api/v1/onboarding/plan-templates
- POST /api/v1/onboarding/plan-templates/{template_id}/tasks
- POST /api/v1/onboarding/employees/{employee_id}/bundle
- GET  /api/v1/onboarding/employees/{employee_id}/bundle
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.db.session import get_db
from app.domains.onboarding.policies import (
    require_onboarding_bundle_read,
    require_onboarding_bundle_write,
    require_onboarding_template_read,
    require_onboarding_template_write,
)
from app.domains.onboarding.schemas import (
    BundleCreateIn,
    BundleDetailOut,
    EmployeeBundleOut,
    EmployeeTaskOut,
    PlanTemplateCreateIn,
    PlanTemplateOut,
    PlanTemplateTaskCreateIn,
    PlanTemplateTaskOut,
)
from app.domains.onboarding.service import (
    OnboardingBundleService,
    OnboardingTemplateService,
)
from app.shared.types import AuthContext


router = APIRouter(prefix="/onboarding", tags=["onboarding"])
_templates = OnboardingTemplateService()
_bundles = OnboardingBundleService()


@router.get("/plan-templates")
def list_plan_templates(
    ctx: AuthContext = Depends(require_onboarding_template_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _templates.list_templates(db, ctx=ctx)
    items = [PlanTemplateOut(**r) for r in rows]
    return ok([i.model_dump() for i in items])


@router.post("/plan-templates")
def create_plan_template(
    payload: PlanTemplateCreateIn,
    ctx: AuthContext = Depends(require_onboarding_template_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _templates.create_template(db, ctx=ctx, payload=payload.model_dump())
    return ok(PlanTemplateOut(**row).model_dump())


@router.post("/plan-templates/{template_id}/tasks")
def add_plan_template_task(
    template_id: UUID,
    payload: PlanTemplateTaskCreateIn,
    ctx: AuthContext = Depends(require_onboarding_template_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _templates.add_task(
        db, ctx=ctx, template_id=template_id, payload=payload.model_dump()
    )
    return ok(PlanTemplateTaskOut(**row).model_dump())


@router.post("/employees/{employee_id}/bundle")
def create_employee_bundle(
    employee_id: UUID,
    payload: BundleCreateIn,
    ctx: AuthContext = Depends(require_onboarding_bundle_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    bundle, tasks = _bundles.create_bundle(
        db,
        ctx=ctx,
        employee_id=employee_id,
        template_code=payload.template_code,
        branch_id=payload.branch_id,
    )
    out = BundleDetailOut(
        bundle=EmployeeBundleOut(**bundle),
        tasks=[EmployeeTaskOut(**t) for t in tasks],
    )
    return ok(out.model_dump())


@router.get("/employees/{employee_id}/bundle")
def get_employee_bundle(
    employee_id: UUID,
    ctx: AuthContext = Depends(require_onboarding_bundle_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    bundle, tasks = _bundles.get_active_bundle_for_employee(
        db, ctx=ctx, employee_id=employee_id
    )
    out = BundleDetailOut(
        bundle=EmployeeBundleOut(**bundle),
        tasks=[EmployeeTaskOut(**t) for t in tasks],
    )
    return ok(out.model_dump())
