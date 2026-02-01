from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.deps import get_auth_context, rate_limit_placeholder
from app.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    ScopeOut,
    TokenResponse,
    UserOut,
)
from app.auth.service import AuthService
from app.core.responses import ok
from app.db.session import get_db
from app.shared.types import AuthContext

router = APIRouter(prefix="/auth", tags=["auth"])
_svc = AuthService()


@router.post("/login")
def login(
    payload: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit_placeholder),
) -> dict[str, object]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")
    tokens, ctx = _svc.login(
        db,
        email=str(payload.email),
        password=payload.password,
        headers=dict(request.headers),
        ip=ip,
        user_agent=ua,
    )
    return ok(
        TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
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


@router.post("/refresh")
def refresh(
    payload: RefreshRequest,
    request: Request,
    db: Session = Depends(get_db),
    _rl: None = Depends(rate_limit_placeholder),
) -> dict[str, object]:
    ip = request.client.host if request.client else None
    ua = request.headers.get("User-Agent")
    tokens, ctx = _svc.refresh(
        db,
        refresh_token=payload.refresh_token,
        headers=dict(request.headers),
        ip=ip,
        user_agent=ua,
    )
    return ok(
        TokenResponse(
            access_token=tokens.access_token,
            refresh_token=tokens.refresh_token,
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


@router.post("/logout")
def logout(payload: LogoutRequest, db: Session = Depends(get_db)) -> dict[str, object]:
    _svc.logout(db, refresh_token=payload.refresh_token)
    return ok({"revoked": True})


@router.get("/me")
def me(ctx: AuthContext = Depends(get_auth_context)) -> dict[str, object]:
    return ok(
        MeResponse(
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

