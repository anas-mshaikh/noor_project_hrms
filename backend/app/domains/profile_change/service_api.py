"""
Profile change API-facing service (Milestone 6).

This module contains the operations used by FastAPI routers:
- resolve ESS actor employee link (409 ess.not_linked)
- create a profile change request + workflow request atomically
- list requests with cursor pagination
- cancel pending requests (participant-only; 404 on deny)

The workflow terminal side-effects are implemented separately in
`service_apply.py` and invoked via workflow hooks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.profile_change.change_set import (
    TOP_LEVEL_KEYS_ORDER,
    normalize_change_set,
)
from app.domains.profile_change.notifications import (
    enqueue_notification,
    list_employee_user_ids,
)
from app.domains.profile_change.utils import json_canonical, utcnow
from app.domains.workflow.service import WorkflowService
from app.shared.types import AuthContext


@dataclass(frozen=True)
class ActorEmployee:
    """
    Small container for actor/tenant identifiers.

    We keep this as a dataclass (instead of a tuple) so call sites are explicit.
    """

    employee_id: UUID
    tenant_id: UUID
    company_id: UUID


class ProfileChangeService:
    """API-facing operations for profile change requests."""

    def __init__(self) -> None:
        self._workflow = WorkflowService()

    # ------------------------------------------------------------------
    # Actor resolution
    # ------------------------------------------------------------------
    def get_actor_employee_or_409(
        self, db: Session, *, ctx: AuthContext
    ) -> ActorEmployee:
        """
        Resolve the employee linked to the current user.

        This mirrors the ESS linkage behavior used across the repo:
        - if not linked: 409 ess.not_linked
        """

        tenant_id = ctx.scope.tenant_id
        row = db.execute(
            sa.text(
                """
                SELECT e.id AS employee_id, e.company_id
                FROM hr_core.employee_user_links l
                JOIN hr_core.employees e ON e.id = l.employee_id
                WHERE l.user_id = :user_id
                  AND e.tenant_id = :tenant_id
                LIMIT 1
                """
            ),
            {"user_id": ctx.user_id, "tenant_id": tenant_id},
        ).first()
        if row is None:
            raise AppError(
                code="ess.not_linked",
                message="User is not linked to an employee",
                status_code=409,
            )
        employee_id, company_id = row
        return ActorEmployee(
            employee_id=UUID(str(employee_id)),
            tenant_id=tenant_id,
            company_id=UUID(str(company_id)),
        )

    def _get_current_employment(
        self, db: Session, *, tenant_id: UUID, employee_id: UUID
    ) -> dict[str, Any]:
        """
        Resolve current employment via the canonical view.

        We use this to ensure workflow scope hints align with the employee's
        current branch/company.
        """

        row = (
            db.execute(
                sa.text(
                    """
                SELECT company_id, branch_id
                FROM hr_core.v_employee_current_employment
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                """
                ),
                {"tenant_id": tenant_id, "employee_id": employee_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(
                code="validation_error",
                message="Employee has no current employment",
                status_code=400,
            )
        return dict(row)

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    def create_profile_change_request(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        change_set: dict[str, Any],
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        """
        Create a domain request + workflow request in one DB transaction.

        Idempotency:
        - If the same (tenant, employee, idempotency_key) exists:
          - same normalized change_set -> return existing
          - different -> 409 hr.profile_change.idempotency_conflict
        """

        actor = self.get_actor_employee_or_409(db, ctx=ctx)
        tenant_id = actor.tenant_id

        employment = self._get_current_employment(
            db, tenant_id=tenant_id, employee_id=actor.employee_id
        )
        employment_company_id = UUID(str(employment["company_id"]))
        employment_branch_id = UUID(str(employment["branch_id"]))

        # Scope hardening: workflow service will also enforce hints match scope,
        # but we fail early with a clearer error message.
        if (
            ctx.scope.company_id is None
            or employment_company_id != ctx.scope.company_id
        ):
            raise AppError(
                code="iam.scope.mismatch",
                message="company_id does not match active scope",
                status_code=400,
            )
        if ctx.scope.branch_id is None or employment_branch_id != ctx.scope.branch_id:
            raise AppError(
                code="iam.scope.mismatch",
                message="branch_id does not match active scope",
                status_code=400,
            )

        normalized = normalize_change_set(change_set)

        # Domain-level idempotency check (preferred over workflow idempotency).
        if idempotency_key:
            existing = (
                db.execute(
                    sa.text(
                        """
                    SELECT *
                    FROM hr_core.profile_change_requests
                    WHERE tenant_id = :tenant_id
                      AND employee_id = :employee_id
                      AND idempotency_key = :key
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "employee_id": actor.employee_id,
                        "key": idempotency_key,
                    },
                )
                .mappings()
                .first()
            )
            if existing is not None:
                same = json_canonical(
                    existing.get("change_set") or {}
                ) == json_canonical(normalized)
                if not same:
                    raise AppError(
                        code="hr.profile_change.idempotency_conflict",
                        message="Idempotency key already used with different payload",
                        status_code=409,
                    )
                return dict(existing)

        request_id = uuid4()
        now = utcnow()

        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO hr_core.profile_change_requests (
                      id, tenant_id, employee_id, created_by_user_id,
                      status, workflow_request_id, change_set, idempotency_key,
                      decided_at, decided_by_user_id,
                      created_at, updated_at
                    ) VALUES (
                      :id, :tenant_id, :employee_id, :created_by_user_id,
                      'PENDING', NULL, CAST(:change_set AS jsonb), :idempotency_key,
                      NULL, NULL,
                      :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": request_id,
                    "tenant_id": tenant_id,
                    "employee_id": actor.employee_id,
                    "created_by_user_id": ctx.user_id,
                    "change_set": json_canonical(normalized),
                    "idempotency_key": idempotency_key,
                    "created_at": now,
                    "updated_at": now,
                },
            )
        except IntegrityError as e:
            # Race on the partial unique idempotency index.
            db.rollback()
            if idempotency_key:
                existing = (
                    db.execute(
                        sa.text(
                            """
                        SELECT *
                        FROM hr_core.profile_change_requests
                        WHERE tenant_id = :tenant_id
                          AND employee_id = :employee_id
                          AND idempotency_key = :key
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                        """
                        ),
                        {
                            "tenant_id": tenant_id,
                            "employee_id": actor.employee_id,
                            "key": idempotency_key,
                        },
                    )
                    .mappings()
                    .first()
                )
                if existing is not None and json_canonical(
                    existing.get("change_set") or {}
                ) == json_canonical(normalized):
                    return dict(existing)
            raise AppError(
                code="hr.profile_change.idempotency_conflict",
                message="Idempotency key already used",
                status_code=409,
            ) from e

        # Compact workflow payload (no PII).
        fields = [k for k in TOP_LEVEL_KEYS_ORDER if k in normalized]
        payload = {
            "subject": "HR Profile Change",
            "fields": fields,
            "counts": {
                "bank_accounts": len(normalized.get("bank_accounts") or []),
                "government_ids": len(normalized.get("government_ids") or []),
                "dependents": len(normalized.get("dependents") or []),
            },
        }

        wf_idem = f"hrpc:{idempotency_key}" if idempotency_key else None
        wf = self._workflow.create_request(
            db,
            ctx=ctx,
            request_type_code="HR_PROFILE_CHANGE",
            payload=payload,
            subject_employee_id=actor.employee_id,
            entity_type="hr_core.profile_change_request",
            entity_id=request_id,
            company_id_hint=employment_company_id,
            branch_id_hint=employment_branch_id,
            idempotency_key=wf_idem,
            initial_comment=None,
            commit=False,
        )
        workflow_request_id = UUID(str(wf["id"]))

        db.execute(
            sa.text(
                """
                UPDATE hr_core.profile_change_requests
                SET workflow_request_id = :workflow_request_id,
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {
                "workflow_request_id": workflow_request_id,
                "tenant_id": tenant_id,
                "id": request_id,
            },
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="hr.profile_change.create",
            entity_type="hr_core.profile_change_request",
            entity_id=request_id,
            before=None,
            after={
                "fields": fields,
                "workflow_request_id": str(workflow_request_id),
                "idempotency_key": idempotency_key,
            },
        )

        # Best-effort: notify the employee that the request was submitted.
        for uid in list_employee_user_ids(db, employee_id=actor.employee_id):
            enqueue_notification(
                db,
                tenant_id=tenant_id,
                recipient_user_id=uid,
                template_code="hr.profile_change.submitted",
                dedupe_key=f"hrpc:submitted:{request_id}:{uid}",
                payload={
                    "title": "Profile change submitted",
                    "body": "Your profile change request was submitted for approval.",
                    "entity_type": "hr_core.profile_change_request",
                    "entity_id": str(request_id),
                    "action_url": f"/ess/profile-change-requests/{request_id}",
                    "correlation_id": ctx.correlation_id,
                },
            )

        db.commit()

        created = (
            db.execute(
                sa.text(
                    """
                SELECT *
                FROM hr_core.profile_change_requests
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
                ),
                {"tenant_id": tenant_id, "id": request_id},
            )
            .mappings()
            .first()
        )
        assert created is not None
        return dict(created)

    # ------------------------------------------------------------------
    # List/read
    # ------------------------------------------------------------------
    def list_my_requests(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        status: str | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """List the actor's own requests (cursor pagination)."""

        actor = self.get_actor_employee_or_409(db, ctx=ctx)
        tenant_id = actor.tenant_id

        where = ["tenant_id = :tenant_id", "employee_id = :employee_id"]
        params: dict[str, Any] = {
            "tenant_id": tenant_id,
            "employee_id": actor.employee_id,
            "limit": int(limit),
        }
        if status:
            where.append("status = :status")
            params["status"] = status
        if cursor is not None:
            ts, cid = cursor
            where.append("(created_at, id) < (:cursor_ts, :cursor_id)")
            params["cursor_ts"] = ts
            params["cursor_id"] = cid

        sql = f"""
            SELECT *
            FROM hr_core.profile_change_requests
            WHERE {" AND ".join(where)}
            ORDER BY created_at DESC, id DESC
            LIMIT :limit
        """
        rows = db.execute(sa.text(sql), params).mappings().all()
        items = [dict(r) for r in rows]
        next_cursor = None
        if len(items) == limit and rows:
            last = rows[-1]
            next_cursor = f"{last['created_at'].isoformat()}|{last['id']}"
        return items, next_cursor

    def list_requests_hr(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        status: str | None,
        branch_id: UUID | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """Tenant-scoped HR list endpoint with optional branch filter."""

        tenant_id = ctx.scope.tenant_id

        # Branch filter uses current employment (v_employee_current_employment).
        joins = ""
        where = ["r.tenant_id = :tenant_id"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": int(limit)}

        if status:
            where.append("r.status = :status")
            params["status"] = status
        if branch_id is not None:
            joins = (
                "JOIN hr_core.v_employee_current_employment ce ON ce.employee_id = r.employee_id "
                "AND ce.tenant_id = r.tenant_id"
            )
            where.append("ce.branch_id = :branch_id")
            params["branch_id"] = branch_id
        if cursor is not None:
            ts, cid = cursor
            where.append("(r.created_at, r.id) < (:cursor_ts, :cursor_id)")
            params["cursor_ts"] = ts
            params["cursor_id"] = cid

        sql = f"""
            SELECT r.*
            FROM hr_core.profile_change_requests r
            {joins}
            WHERE {" AND ".join(where)}
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT :limit
        """
        rows = db.execute(sa.text(sql), params).mappings().all()
        items = [dict(r) for r in rows]
        next_cursor = None
        if len(items) == limit and rows:
            last = rows[-1]
            next_cursor = f"{last['created_at'].isoformat()}|{last['id']}"
        return items, next_cursor

    # ------------------------------------------------------------------
    # Cancel
    # ------------------------------------------------------------------
    def cancel_my_request(
        self, db: Session, *, ctx: AuthContext, request_id: UUID
    ) -> dict[str, Any]:
        """Cancel a pending request (participant-only)."""

        actor = self.get_actor_employee_or_409(db, ctx=ctx)
        tenant_id = actor.tenant_id

        row = (
            db.execute(
                sa.text(
                    """
                SELECT id, status, workflow_request_id
                FROM hr_core.profile_change_requests
                WHERE tenant_id = :tenant_id
                  AND id = :id
                  AND employee_id = :employee_id
                """
                ),
                {
                    "tenant_id": tenant_id,
                    "id": request_id,
                    "employee_id": actor.employee_id,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(
                code="hr.profile_change.not_found",
                message="Profile change request not found",
                status_code=404,
            )

        if str(row["status"]) != "PENDING":
            raise AppError(
                code="hr.profile_change.already_terminal",
                message="Profile change request is not pending",
                status_code=409,
            )

        wf_raw = row.get("workflow_request_id")
        if wf_raw is None:
            raise AppError(
                code="validation_error",
                message="Request has no workflow_request_id",
                status_code=500,
            )

        wf_id = UUID(str(wf_raw))

        # WorkflowService.cancel_request commits and invokes domain hooks.
        self._workflow.cancel_request(db, ctx=ctx, request_id=wf_id)

        refreshed = (
            db.execute(
                sa.text(
                    """
                SELECT *
                FROM hr_core.profile_change_requests
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
                ),
                {"tenant_id": tenant_id, "id": request_id},
            )
            .mappings()
            .first()
        )
        assert refreshed is not None
        return dict(refreshed)


def parse_cursor(cursor: str) -> tuple[datetime, UUID]:
    """
    Parse a cursor of the form "ts|uuid".

    We keep this helper next to the list/read paths so cursor formatting remains
    consistent across callers.
    """

    try:
        ts_raw, id_raw = cursor.split("|", 1)
        ts = datetime.fromisoformat(ts_raw)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts, UUID(id_raw)
    except Exception as e:  # noqa: BLE001 - stable AppError for clients
        raise AppError(
            code="validation_error",
            message=f"invalid cursor: {cursor!r}",
            status_code=400,
        ) from e
