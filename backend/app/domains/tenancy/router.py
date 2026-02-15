from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.deps import require_permission
from app.auth.permissions import TENANCY_READ, TENANCY_WRITE
from app.auth.schemas import ScopeOut, TokenResponse, UserOut
from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.tenancy.schemas import (
    BootstrapRequest,
    BranchCreate,
    BranchOut,
    CompanyCreate,
    CompanyOut,
    GradeCreate,
    GradeOut,
    JobTitleCreate,
    JobTitleOut,
    OrgUnitCreate,
    OrgUnitOut,
)
from app.domains.tenancy.service import TenancyService
from app.shared.types import AuthContext

router = APIRouter(tags=["tenancy"])
_svc = TenancyService()


@router.post("/bootstrap")
def bootstrap(payload: BootstrapRequest, request: Request, db: Session = Depends(get_db)) -> dict[str, object]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")

    result = _svc.bootstrap(
        db,
        tenant_name=payload.tenant_name,
        company_name=payload.company_name,
        branch_name=payload.branch_name,
        branch_code=payload.branch_code,
        timezone_name=payload.timezone,
        currency_code=payload.currency_code,
        admin_email=str(payload.admin_email),
        admin_password=payload.admin_password,
        ip=ip,
        user_agent=ua,
    )
    ctx = result.ctx
    return ok(
        TokenResponse(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            user=UserOut(id=ctx.user_id, email=ctx.email, status=ctx.status),
            roles=list(ctx.roles),
            scope=ScopeOut(
                tenant_id=ctx.scope.tenant_id,
                company_id=ctx.scope.company_id,
                branch_id=ctx.scope.branch_id,
                allowed_tenant_ids=list(ctx.scope.allowed_tenant_ids),
                allowed_company_ids=list(ctx.scope.allowed_company_ids),
                allowed_branch_ids=list(ctx.scope.allowed_branch_ids),
            ),
        ).model_dump()
    )


@router.get("/tenancy/companies")
def list_companies(
    ctx: AuthContext = Depends(require_permission(TENANCY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    companies = _svc.list_companies(db, tenant_id=ctx.scope.tenant_id)
    return ok(
        [
            CompanyOut(
                id=c.id,
                tenant_id=c.tenant_id,
                name=c.name,
                legal_name=c.legal_name,
                currency_code=c.currency_code,
                timezone=c.timezone,
                status=c.status,
            ).model_dump()
            for c in companies
        ]
    )


@router.post("/tenancy/companies")
def create_company(
    payload: CompanyCreate,
    ctx: AuthContext = Depends(require_permission(TENANCY_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    c = _svc.create_company(
        db,
        tenant_id=ctx.scope.tenant_id,
        name=payload.name,
        legal_name=payload.legal_name,
        currency_code=payload.currency_code,
        timezone_name=payload.timezone,
    )
    return ok(
        CompanyOut(
            id=c.id,
            tenant_id=c.tenant_id,
            name=c.name,
            legal_name=c.legal_name,
            currency_code=c.currency_code,
            timezone=c.timezone,
            status=c.status,
        ).model_dump()
    )


@router.get("/tenancy/branches")
def list_branches(
    company_id: UUID | None = None,
    ctx: AuthContext = Depends(require_permission(TENANCY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    branches = _svc.list_branches(db, tenant_id=ctx.scope.tenant_id, company_id=company_id)
    return ok(
        [
            BranchOut(
                id=b.id,
                tenant_id=b.tenant_id,
                company_id=b.company_id,
                name=b.name,
                code=b.code,
                timezone=b.timezone,
                address=b.address,
                status=b.status,
            ).model_dump()
            for b in branches
        ]
    )


@router.post("/tenancy/branches")
def create_branch(
    payload: BranchCreate,
    ctx: AuthContext = Depends(require_permission(TENANCY_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    b = _svc.create_branch(
        db,
        tenant_id=ctx.scope.tenant_id,
        company_id=payload.company_id,
        name=payload.name,
        code=payload.code,
        timezone_name=payload.timezone,
        address=payload.address,
    )
    return ok(
        BranchOut(
            id=b.id,
            tenant_id=b.tenant_id,
            company_id=b.company_id,
            name=b.name,
            code=b.code,
            timezone=b.timezone,
            address=b.address,
            status=b.status,
        ).model_dump()
    )


@router.get("/tenancy/org-units")
def list_org_units(
    company_id: UUID,
    branch_id: UUID | None = None,
    ctx: AuthContext = Depends(require_permission(TENANCY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    units = _svc.list_org_units(
        db,
        tenant_id=ctx.scope.tenant_id,
        company_id=company_id,
        branch_id=branch_id,
    )
    return ok(
        [
            OrgUnitOut(
                id=u.id,
                tenant_id=u.tenant_id,
                company_id=u.company_id,
                branch_id=u.branch_id,
                parent_id=u.parent_id,
                name=u.name,
                unit_type=u.unit_type,
            ).model_dump()
            for u in units
        ]
    )


@router.post("/tenancy/org-units")
def create_org_unit(
    payload: OrgUnitCreate,
    ctx: AuthContext = Depends(require_permission(TENANCY_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    u = _svc.create_org_unit(
        db,
        tenant_id=ctx.scope.tenant_id,
        company_id=payload.company_id,
        branch_id=payload.branch_id,
        parent_id=payload.parent_id,
        name=payload.name,
        unit_type=payload.unit_type,
    )
    return ok(
        OrgUnitOut(
            id=u.id,
            tenant_id=u.tenant_id,
            company_id=u.company_id,
            branch_id=u.branch_id,
            parent_id=u.parent_id,
            name=u.name,
            unit_type=u.unit_type,
        ).model_dump()
    )


@router.get("/tenancy/org-chart")
def org_chart(
    company_id: UUID,
    branch_id: UUID | None = None,
    ctx: AuthContext = Depends(require_permission(TENANCY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    tree = _svc.build_org_chart(
        db,
        tenant_id=ctx.scope.tenant_id,
        company_id=company_id,
        branch_id=branch_id,
    )
    return ok(tree)


def _require_company_id(ctx: AuthContext, company_id: UUID | None) -> UUID:
    cid = company_id or ctx.scope.company_id
    if cid is None:
        raise AppError(code="invalid_scope", message="company_id is required", status_code=400)
    return cid


@router.get("/tenancy/job-titles")
def list_job_titles(
    company_id: UUID | None = None,
    ctx: AuthContext = Depends(require_permission(TENANCY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cid = _require_company_id(ctx, company_id)
    rows = _svc.list_job_titles(db, tenant_id=ctx.scope.tenant_id, company_id=cid)
    return ok([JobTitleOut(id=r.id, tenant_id=r.tenant_id, company_id=r.company_id, name=r.name).model_dump() for r in rows])


@router.post("/tenancy/job-titles")
def create_job_title(
    payload: JobTitleCreate,
    ctx: AuthContext = Depends(require_permission(TENANCY_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    jt = _svc.create_job_title(
        db,
        tenant_id=ctx.scope.tenant_id,
        company_id=payload.company_id,
        name=payload.name,
    )
    return ok(JobTitleOut(id=jt.id, tenant_id=jt.tenant_id, company_id=jt.company_id, name=jt.name).model_dump())


@router.get("/tenancy/grades")
def list_grades(
    company_id: UUID | None = None,
    ctx: AuthContext = Depends(require_permission(TENANCY_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cid = _require_company_id(ctx, company_id)
    rows = _svc.list_grades(db, tenant_id=ctx.scope.tenant_id, company_id=cid)
    return ok(
        [
            GradeOut(id=r.id, tenant_id=r.tenant_id, company_id=r.company_id, name=r.name, level=r.level).model_dump()
            for r in rows
        ]
    )


@router.post("/tenancy/grades")
def create_grade(
    payload: GradeCreate,
    ctx: AuthContext = Depends(require_permission(TENANCY_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    g = _svc.create_grade(
        db,
        tenant_id=ctx.scope.tenant_id,
        company_id=payload.company_id,
        name=payload.name,
        level=payload.level,
    )
    return ok(GradeOut(id=g.id, tenant_id=g.tenant_id, company_id=g.company_id, name=g.name, level=g.level).model_dump())
