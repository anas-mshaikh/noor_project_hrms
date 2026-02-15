from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.responses import ok
from app.db.session import get_db
from app.domains.hr_core.policies import require_ess_read, require_ess_write
from app.domains.hr_core.schemas import EssProfilePatchIn
from app.domains.hr_core.service import HRCoreService
from app.shared.types import AuthContext

router = APIRouter(prefix="/ess", tags=["ESS"])
_svc = HRCoreService()


@router.get("/me/profile")
def me_profile(
    ctx: AuthContext = Depends(require_ess_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    out = _svc.ess_get_profile(db, ctx=ctx)
    return ok(out.model_dump())


@router.patch("/me/profile")
def patch_me_profile(
    payload: EssProfilePatchIn,
    ctx: AuthContext = Depends(require_ess_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    out = _svc.ess_patch_profile(db, ctx=ctx, payload=payload)
    return ok(out.model_dump())
