from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.db.session import get_db
from app.domains.hr_core.policies import require_mss_access
from app.domains.hr_core.schemas import MSSEmployeeProfileOut, MSSTeamListOut, PagingOut
from app.domains.hr_core.service_mss import MSSService
from app.shared.types import AuthContext

router = APIRouter(prefix="/mss", tags=["MSS"])
_svc = MSSService()


@router.get("/team")
def team_list(
    depth: str = Query("1"),
    q: str | None = Query(default=None, min_length=1),
    status: str | None = Query(default=None, min_length=1),
    branch_id: UUID | None = None,
    org_unit_id: UUID | None = None,
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    ctx: AuthContext = Depends(require_mss_access),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items, total = _svc.list_team(
        db,
        ctx=ctx,
        depth=depth,
        q=q,
        status=status,
        branch_id=branch_id,
        org_unit_id=org_unit_id,
        limit=limit,
        offset=offset,
    )
    out = MSSTeamListOut(items=items, paging=PagingOut(limit=limit, offset=offset, total=total))
    return ok(out.model_dump())


@router.get("/team/{employee_id}")
def team_member_profile(
    employee_id: UUID,
    ctx: AuthContext = Depends(require_mss_access),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    out = _svc.get_team_member_profile(db, ctx=ctx, employee_id=employee_id)
    return ok(out.model_dump())
