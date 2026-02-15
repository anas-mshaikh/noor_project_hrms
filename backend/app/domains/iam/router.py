from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.auth.deps import require_permission
from app.auth.permissions import IAM_PERMISSION_READ, IAM_ROLE_ASSIGN
from app.core.responses import ok
from app.db.session import get_db
from app.domains.iam.policies import require_iam_read, require_iam_write
from app.domains.iam.schemas import (
    PermissionOut,
    RoleAssignIn,
    RoleOut,
    UserCreateIn,
    UserOut,
    UserPatchIn,
    UserRoleOut,
)
from app.domains.iam.service import IAMService
from app.shared.types import AuthContext

router = APIRouter(prefix="/iam", tags=["IAM"])
_svc = IAMService()


@router.post("/users")
def create_user(
    payload: UserCreateIn,
    ctx: AuthContext = Depends(require_iam_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    user = _svc.create_user(db, ctx=ctx, payload=payload)
    return ok(
        UserOut(
            id=user.id,
            email=user.email,
            phone=user.phone,
            status=user.status,
            created_at=user.created_at,
        ).model_dump()
    )


@router.get("/users")
def list_users(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    q: str | None = Query(default=None, min_length=1),
    status: str | None = Query(default=None, min_length=1),
    ctx: AuthContext = Depends(require_iam_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    items, total = _svc.list_users(db, ctx=ctx, q=q, status=status, limit=limit, offset=offset)
    return ok(
        [
            UserOut(id=u.id, email=u.email, phone=u.phone, status=u.status, created_at=u.created_at).model_dump()
            for u in items
        ],
        meta={"limit": limit, "offset": offset, "total": total},
    )


@router.get("/users/{user_id}")
def get_user(
    user_id: UUID,
    ctx: AuthContext = Depends(require_iam_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    u = _svc.get_user(db, ctx=ctx, user_id=user_id)
    return ok(UserOut(id=u.id, email=u.email, phone=u.phone, status=u.status, created_at=u.created_at).model_dump())


@router.patch("/users/{user_id}")
def patch_user(
    user_id: UUID,
    payload: UserPatchIn,
    ctx: AuthContext = Depends(require_iam_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    u = _svc.patch_user(db, ctx=ctx, user_id=user_id, payload=payload)
    return ok(UserOut(id=u.id, email=u.email, phone=u.phone, status=u.status, created_at=u.created_at).model_dump())


@router.post("/users/{user_id}/roles")
def assign_role(
    user_id: UUID,
    payload: RoleAssignIn,
    ctx: AuthContext = Depends(require_permission(IAM_ROLE_ASSIGN)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ur, role_code = _svc.assign_role(db, ctx=ctx, user_id=user_id, payload=payload)
    return ok(
        UserRoleOut(
            role_code=role_code,
            tenant_id=ur.tenant_id,
            company_id=ur.company_id,
            branch_id=ur.branch_id,
            created_at=ur.created_at,
        ).model_dump()
    )


@router.get("/users/{user_id}/roles")
def list_user_roles(
    user_id: UUID,
    ctx: AuthContext = Depends(require_iam_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _svc.list_user_roles(db, ctx=ctx, user_id=user_id)
    return ok(
        [
            UserRoleOut(
                role_code=role_code,
                tenant_id=tenant_id,
                company_id=company_id,
                branch_id=branch_id,
                created_at=created_at,
            ).model_dump()
            for (role_code, tenant_id, company_id, branch_id, created_at) in rows
        ]
    )


@router.delete("/users/{user_id}/roles")
def delete_user_role(
    user_id: UUID,
    role_code: str = Query(..., min_length=1),
    company_id: UUID | None = None,
    branch_id: UUID | None = None,
    ctx: AuthContext = Depends(require_permission(IAM_ROLE_ASSIGN)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _svc.remove_role(db, ctx=ctx, user_id=user_id, role_code=role_code, company_id=company_id, branch_id=branch_id)
    return ok({"deleted": True})


@router.get("/roles")
def list_roles(
    ctx: AuthContext = Depends(require_iam_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    roles = _svc.list_roles(db)
    return ok([RoleOut(code=r.code, name=r.name, description=r.description).model_dump() for r in roles])


@router.get("/permissions")
def list_permissions(
    ctx: AuthContext = Depends(require_permission(IAM_PERMISSION_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    perms = _svc.list_permissions(db)
    return ok([PermissionOut(code=code, description=desc).model_dump() for code, desc in perms])
