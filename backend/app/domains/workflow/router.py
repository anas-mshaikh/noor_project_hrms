from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.domains.workflow.policies import (
    require_workflow_definition_read,
    require_workflow_definition_write,
    require_workflow_request_approve,
    require_workflow_request_read,
    require_workflow_request_submit,
)
from app.domains.workflow.schemas import (
    WorkflowAttachmentCreateIn,
    WorkflowCommentCreateIn,
    WorkflowDefinitionCreateIn,
    WorkflowDefinitionOut,
    WorkflowDefinitionStepsIn,
    WorkflowRequestApproveIn,
    WorkflowRequestCreateIn,
    WorkflowRequestDetailOut,
    WorkflowRequestListOut,
    WorkflowRequestRejectIn,
    WorkflowRequestSummaryOut,
)
from app.domains.workflow.service import WorkflowService, db_to_api_status
from app.shared.types import AuthContext
from app.auth.permissions import DMS_FILE_READ


router = APIRouter(prefix="/workflow", tags=["workflow"])
_svc = WorkflowService()


def _parse_cursor(cursor: str) -> tuple[datetime, UUID]:
    try:
        ts_raw, id_raw = cursor.split("|", 1)
        ts = datetime.fromisoformat(ts_raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts, UUID(id_raw)
    except Exception as e:
        raise AppError(code="validation_error", message=f"invalid cursor: {cursor!r}", status_code=400) from e


@router.post("/requests")
def create_request(
    payload: WorkflowRequestCreateIn,
    ctx: AuthContext = Depends(require_workflow_request_submit),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    row = _svc.create_request(
        db,
        ctx=ctx,
        request_type_code=payload.request_type_code,
        payload=payload.payload,
        subject_employee_id=payload.subject_employee_id,
        entity_type=payload.entity_type,
        entity_id=payload.entity_id,
        company_id_hint=payload.company_id,
        branch_id_hint=payload.branch_id,
        idempotency_key=payload.idempotency_key,
        initial_comment=payload.comment,
    )

    out = WorkflowRequestSummaryOut(
        id=row["id"],
        request_type_code=str(row["request_type_code"]),
        status=db_to_api_status(str(row["status"])),
        current_step=int(row["current_step"]),
        subject=row.get("subject"),
        payload=row.get("payload"),
        tenant_id=row["tenant_id"],
        company_id=row["company_id"],
        branch_id=row.get("branch_id"),
        created_by_user_id=row.get("created_by_user_id"),
        requester_employee_id=row["requester_employee_id"],
        subject_employee_id=row.get("subject_employee_id"),
        entity_type=row.get("entity_type"),
        entity_id=row.get("entity_id"),
        created_at=row.get("created_at") or datetime.now(timezone.utc),
        updated_at=row.get("updated_at") or datetime.now(timezone.utc),
    )
    return ok(out.model_dump())


@router.get("/requests/{request_id}")
def get_request(
    request_id: UUID,
    ctx: AuthContext = Depends(require_workflow_request_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    data = _svc.get_request_detail(db, ctx=ctx, request_id=request_id)

    req = data["request"]
    steps = data["steps"]
    assignees_by_step = data["assignees_by_step"]

    req_out = WorkflowRequestSummaryOut(
        id=req["id"],
        request_type_code=str(req["request_type_code"]),
        status=db_to_api_status(str(req["status"])),
        current_step=int(req["current_step"]),
        subject=req.get("subject"),
        payload=req.get("payload") or {},
        tenant_id=req["tenant_id"],
        company_id=req["company_id"],
        branch_id=req.get("branch_id"),
        created_by_user_id=req.get("created_by_user_id"),
        requester_employee_id=req["requester_employee_id"],
        subject_employee_id=req.get("subject_employee_id"),
        entity_type=req.get("entity_type"),
        entity_id=req.get("entity_id"),
        created_at=req["created_at"],
        updated_at=req["updated_at"],
    )

    step_out = []
    for s in steps:
        sid = UUID(str(s["id"]))
        assignee_user_ids = assignees_by_step.get(sid, [])
        decided_by = s.get("approver_user_id") if s.get("decision") is not None else None
        step_out.append(
            {
                "id": sid,
                "step_order": int(s["step_order"]),
                "assignee_type": s.get("assignee_type"),
                "assignee_role_code": s.get("assignee_role_code"),
                "assignee_user_id": s.get("assignee_user_id"),
                "assignee_user_ids": assignee_user_ids,
                "decision": s.get("decision"),
                "decided_at": s.get("decided_at"),
                "decided_by_user_id": decided_by,
                "comment": s.get("comment"),
                "created_at": s.get("created_at"),
            }
        )

    detail = WorkflowRequestDetailOut(
        request=req_out,
        steps=step_out,
        comments=[
            {
                "id": c["id"],
                "author_user_id": c["author_user_id"],
                "body": c["body"],
                "created_at": c["created_at"],
            }
            for c in data["comments"]
        ],
        attachments=[
            {
                "id": a["id"],
                "file_id": a["file_id"],
                "uploaded_by_user_id": a.get("created_by"),
                "note": a.get("note"),
                "created_at": a["created_at"],
            }
            for a in data["attachments"]
        ],
        events=[
            {
                "id": e["id"],
                "actor_user_id": e.get("actor_user_id"),
                "event_type": e["event_type"],
                "data": e.get("data") or {},
                "correlation_id": e.get("correlation_id"),
                "created_at": e["created_at"],
            }
            for e in data["events"]
        ],
    )
    return ok(detail.model_dump())


@router.get("/inbox")
def inbox(
    status: str = Query("pending"),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    type: str | None = Query(default=None, alias="type", min_length=1),
    company_id: UUID | None = Query(default=None),
    branch_id: UUID | None = Query(default=None),
    ctx: AuthContext = Depends(require_workflow_request_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    # Only "pending" inbox is supported in v1.
    if status.lower() not in ("pending", "submitted"):
        raise AppError(code="validation_error", message="inbox only supports status=pending", status_code=400)

    cur = _parse_cursor(cursor) if cursor else None
    rows = _svc.list_inbox(
        db,
        ctx=ctx,
        request_type_code=type,
        company_id=company_id,
        branch_id=branch_id,
        limit=limit,
        cursor=cur,
    )

    items = [
        WorkflowRequestSummaryOut(
            id=r["id"],
            request_type_code=str(r["request_type_code"]),
            status=db_to_api_status(str(r["status"])),
            current_step=int(r["current_step"]),
            subject=r.get("subject"),
            payload=None,
            tenant_id=r["tenant_id"],
            company_id=r["company_id"],
            branch_id=r.get("branch_id"),
            created_by_user_id=r.get("created_by_user_id"),
            requester_employee_id=r["requester_employee_id"],
            subject_employee_id=r.get("subject_employee_id"),
            entity_type=r.get("entity_type"),
            entity_id=r.get("entity_id"),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]

    next_cursor = None
    if len(items) == int(limit) and items:
        last = items[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"
    return ok(WorkflowRequestListOut(items=items, next_cursor=next_cursor).model_dump())


@router.get("/outbox")
def outbox(
    status: str | None = Query(default=None),
    limit: int = Query(50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    type: str | None = Query(default=None, alias="type", min_length=1),
    ctx: AuthContext = Depends(require_workflow_request_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    cur = _parse_cursor(cursor) if cursor else None
    rows = _svc.list_outbox(
        db,
        ctx=ctx,
        status=status,
        request_type_code=type,
        limit=limit,
        cursor=cur,
    )

    items = [
        WorkflowRequestSummaryOut(
            id=r["id"],
            request_type_code=str(r["request_type_code"]),
            status=db_to_api_status(str(r["status"])),
            current_step=int(r["current_step"]),
            subject=r.get("subject"),
            payload=None,
            tenant_id=r["tenant_id"],
            company_id=r["company_id"],
            branch_id=r.get("branch_id"),
            created_by_user_id=r.get("created_by_user_id"),
            requester_employee_id=r["requester_employee_id"],
            subject_employee_id=r.get("subject_employee_id"),
            entity_type=r.get("entity_type"),
            entity_id=r.get("entity_id"),
            created_at=r["created_at"],
            updated_at=r["updated_at"],
        )
        for r in rows
    ]

    next_cursor = None
    if len(items) == int(limit) and items:
        last = items[-1]
        next_cursor = f"{last.created_at.isoformat()}|{last.id}"
    return ok(WorkflowRequestListOut(items=items, next_cursor=next_cursor).model_dump())


@router.post("/requests/{request_id}/cancel")
def cancel(
    request_id: UUID,
    ctx: AuthContext = Depends(require_workflow_request_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    res = _svc.cancel_request(db, ctx=ctx, request_id=request_id)
    return ok(res)


@router.post("/requests/{request_id}/approve")
def approve(
    request_id: UUID,
    payload: WorkflowRequestApproveIn,
    ctx: AuthContext = Depends(require_workflow_request_approve),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    res = _svc.approve_request(db, ctx=ctx, request_id=request_id, comment=payload.comment)
    return ok(res)


@router.post("/requests/{request_id}/reject")
def reject(
    request_id: UUID,
    payload: WorkflowRequestRejectIn,
    ctx: AuthContext = Depends(require_workflow_request_approve),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    res = _svc.reject_request(db, ctx=ctx, request_id=request_id, comment=payload.comment)
    return ok(res)


@router.post("/requests/{request_id}/comments")
def add_comment(
    request_id: UUID,
    payload: WorkflowCommentCreateIn,
    ctx: AuthContext = Depends(require_workflow_request_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    res = _svc.add_comment(db, ctx=ctx, request_id=request_id, body=payload.body)
    return ok(res)


@router.post("/requests/{request_id}/attachments")
def add_attachment(
    request_id: UUID,
    payload: WorkflowAttachmentCreateIn,
    ctx: AuthContext = Depends(require_workflow_request_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    if DMS_FILE_READ not in ctx.permissions:
        # Keep consistent with existing permission failures.
        raise AppError(code="forbidden", message="Insufficient permission", status_code=403)

    res = _svc.add_attachment(db, ctx=ctx, request_id=request_id, file_id=payload.file_id, note=payload.note)
    return ok(res)


@router.get("/definitions")
def list_definitions(
    company_id: UUID | None = Query(default=None),
    ctx: AuthContext = Depends(require_workflow_definition_read),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    rows = _svc.list_definitions(db, ctx=ctx, company_id=company_id)

    items: list[WorkflowDefinitionOut] = []
    for d in rows:
        steps = []
        for s in d.get("steps") or []:
            steps.append(
                {
                    "step_index": int(s["step_order"]),
                    "assignee_type": str(s["approver_mode"]),
                    "assignee_role_code": s.get("role_code"),
                    "assignee_user_id": s.get("user_id"),
                    "scope_mode": s.get("scope_mode") or "TENANT",
                    "fallback_role_code": s.get("fallback_role_code"),
                }
            )

        items.append(
            WorkflowDefinitionOut(
                id=d["id"],
                tenant_id=d["tenant_id"],
                company_id=d.get("company_id"),
                request_type_code=str(d["request_type_code"]),
                code=d.get("code"),
                name=str(d["name"]),
                version=d.get("version"),
                is_active=bool(d["is_active"]),
                created_by_user_id=d.get("created_by_user_id"),
                created_at=d["created_at"],
                updated_at=d["updated_at"],
                steps=steps,
            )
        )

    return ok([i.model_dump() for i in items])


@router.post("/definitions")
def create_definition(
    payload: WorkflowDefinitionCreateIn,
    ctx: AuthContext = Depends(require_workflow_definition_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    company_id = payload.company_id if payload.company_id is not None else ctx.scope.company_id
    row = _svc.create_definition(
        db,
        ctx=ctx,
        request_type_code=payload.request_type_code,
        code=payload.code,
        name=payload.name,
        version=payload.version,
        company_id=company_id,
    )
    out = WorkflowDefinitionOut(
        id=row["id"],
        tenant_id=row["tenant_id"],
        company_id=row.get("company_id"),
        request_type_code=str(row["request_type_code"]),
        code=row.get("code"),
        name=str(row["name"]),
        version=row.get("version"),
        is_active=bool(row.get("is_active")),
        created_by_user_id=row.get("created_by_user_id"),
        created_at=row.get("created_at") or datetime.now(timezone.utc),
        updated_at=row.get("updated_at") or datetime.now(timezone.utc),
        steps=[],
    )
    return ok(out.model_dump())


@router.post("/definitions/{definition_id}/steps")
def replace_steps(
    definition_id: UUID,
    payload: WorkflowDefinitionStepsIn,
    ctx: AuthContext = Depends(require_workflow_definition_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    steps_sorted = sorted(payload.steps, key=lambda s: s.step_index)
    for i, s in enumerate(steps_sorted):
        if s.step_index != i:
            raise AppError(code="validation_error", message="steps must be sequential starting at 0", status_code=400)
    _svc.replace_definition_steps(
        db,
        ctx=ctx,
        definition_id=definition_id,
        steps=[s.model_dump() for s in steps_sorted],
    )
    return ok({"updated": True})


@router.post("/definitions/{definition_id}/activate")
def activate(
    definition_id: UUID,
    ctx: AuthContext = Depends(require_workflow_definition_write),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    _svc.activate_definition(db, ctx=ctx, definition_id=definition_id)
    return ok({"activated": True})
