from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.shared.types import AuthContext


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json_canonical(value: Any) -> str:
    # Stable JSON for idempotency comparisons.
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def db_to_api_status(db_status: str) -> str:
    s = (db_status or "").lower()
    if s == "submitted":
        return "PENDING"
    if s == "approved":
        return "APPROVED"
    if s == "rejected":
        return "REJECTED"
    if s == "cancelled":
        return "CANCELED"
    if s == "draft":
        return "DRAFT"
    return s.upper() or "UNKNOWN"


def api_to_db_status(api_status: str) -> str:
    s = (api_status or "").strip().lower()
    if s in ("pending", "submitted"):
        return "submitted"
    if s in ("approved",):
        return "approved"
    if s in ("rejected",):
        return "rejected"
    if s in ("canceled", "cancelled"):
        return "cancelled"
    if s in ("draft",):
        return "draft"
    raise AppError(code="validation_error", message=f"Invalid status: {api_status!r}", status_code=400)


class WorkflowService:
    # -------------------------
    # Request types / definitions
    # -------------------------
    def _get_request_type(self, db: Session, *, request_type_code: str) -> dict[str, Any]:
        row = db.execute(
            sa.text(
                """
                SELECT id, code, name
                FROM workflow.request_types
                WHERE code = :code
                """
            ),
            {"code": request_type_code},
        ).mappings().first()
        if row is None:
            raise AppError(
                code="workflow.request_type.not_found",
                message="Request type not found",
                status_code=404,
            )
        return dict(row)

    def _get_active_definition_id(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        company_id: UUID,
        request_type_id: UUID,
    ) -> UUID:
        # Prefer company-specific active definition; fall back to tenant-wide (company_id IS NULL).
        row = db.execute(
            sa.text(
                """
                SELECT id
                FROM workflow.workflow_definitions
                WHERE tenant_id = :tenant_id
                  AND request_type_id = :request_type_id
                  AND is_active = true
                  AND company_id = :company_id
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id, "request_type_id": request_type_id, "company_id": company_id},
        ).first()
        if row is not None:
            return row[0]

        row2 = db.execute(
            sa.text(
                """
                SELECT id
                FROM workflow.workflow_definitions
                WHERE tenant_id = :tenant_id
                  AND request_type_id = :request_type_id
                  AND is_active = true
                  AND company_id IS NULL
                ORDER BY updated_at DESC, id DESC
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id, "request_type_id": request_type_id},
        ).first()
        if row2 is not None:
            return row2[0]

        raise AppError(
            code="workflow.definition.no_active",
            message="No active workflow definition for this request type",
            status_code=400,
        )

    def _load_definition_steps(self, db: Session, *, definition_id: UUID) -> list[dict[str, Any]]:
        rows = db.execute(
            sa.text(
                """
                SELECT
                  id,
                  step_order,
                  approver_mode,
                  role_code,
                  user_id,
                  scope_mode,
                  fallback_role_code
                FROM workflow.workflow_definition_steps
                WHERE workflow_definition_id = :definition_id
                ORDER BY step_order ASC
                """
            ),
            {"definition_id": definition_id},
        ).mappings().all()
        return [dict(r) for r in rows]

    # -------------------------
    # Assignee resolution
    # -------------------------
    def _resolve_requester_employee_id(self, db: Session, *, user_id: UUID) -> UUID | None:
        row = db.execute(
            sa.text(
                """
                SELECT employee_id
                FROM hr_core.employee_user_links
                WHERE user_id = :user_id
                LIMIT 1
                """
            ),
            {"user_id": user_id},
        ).first()
        return row[0] if row is not None else None

    def _resolve_manager_user_id(self, db: Session, *, tenant_id: UUID, employee_id: UUID) -> UUID | None:
        mgr_emp = db.execute(
            sa.text(
                """
                SELECT manager_employee_id
                FROM hr_core.v_employee_current_employment
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id},
        ).scalar()
        if mgr_emp is None:
            return None
        mgr_user = db.execute(
            sa.text(
                """
                SELECT user_id
                FROM hr_core.employee_user_links
                WHERE employee_id = :employee_id
                LIMIT 1
                """
            ),
            {"employee_id": mgr_emp},
        ).scalar()
        if mgr_user is None:
            return None
        return UUID(str(mgr_user))

    def _resolve_role_user_ids(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        company_id: UUID,
        branch_id: UUID | None,
        role_code: str,
    ) -> list[UUID]:
        # Locked predicate:
        # - tenant-wide: (company_id IS NULL AND branch_id IS NULL)
        # - company-wide: (company_id = :company_id AND branch_id IS NULL)
        # - branch-only: (company_id = :company_id AND branch_id = :branch_id) when branch_id present
        rows = db.execute(
            sa.text(
                """
                SELECT DISTINCT ur.user_id
                FROM iam.user_roles ur
                JOIN iam.roles r ON r.id = ur.role_id
                WHERE ur.tenant_id = :tenant_id
                  AND r.code = :role_code
                  AND (
                    (ur.company_id IS NULL AND ur.branch_id IS NULL)
                    OR (ur.company_id = :company_id AND ur.branch_id IS NULL)
                    OR (ur.company_id = :company_id AND CAST(:branch_id AS uuid) IS NOT NULL AND ur.branch_id = :branch_id)
                  )
                ORDER BY ur.user_id
                """
            ),
            {"tenant_id": tenant_id, "company_id": company_id, "branch_id": branch_id, "role_code": role_code},
        ).all()
        return [UUID(str(r[0])) for r in rows]

    # -------------------------
    # Events / outbox
    # -------------------------
    def _insert_event(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        request_id: UUID,
        actor_user_id: UUID | None,
        event_type: str,
        data: dict[str, Any] | None,
        correlation_id: str | None,
    ) -> None:
        db.execute(
            sa.text(
                """
                INSERT INTO workflow.request_events (
                  tenant_id, request_id, actor_user_id, event_type, data, correlation_id
                ) VALUES (
                  :tenant_id, :request_id, :actor_user_id, :event_type, CAST(:data AS jsonb), :correlation_id
                )
                """
            ),
            {
                "tenant_id": tenant_id,
                "request_id": request_id,
                "actor_user_id": actor_user_id,
                "event_type": event_type,
                "data": _json_canonical(data or {}),
                "correlation_id": correlation_id,
            },
        )

    def _enqueue_in_app_notification(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        recipient_user_id: UUID,
        template_code: str,
        dedupe_key: str,
        payload: dict[str, Any],
    ) -> None:
        db.execute(
            sa.text(
                """
                INSERT INTO workflow.notification_outbox (
                  tenant_id, channel, recipient_user_id, template_code, payload, dedupe_key
                ) VALUES (
                  :tenant_id, 'IN_APP', :recipient_user_id, :template_code, CAST(:payload AS jsonb), :dedupe_key
                )
                -- Match the partial unique index on (tenant_id, channel, dedupe_key) where dedupe_key IS NOT NULL.
                ON CONFLICT (tenant_id, channel, dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
                """
            ),
            {
                "tenant_id": tenant_id,
                "recipient_user_id": recipient_user_id,
                "template_code": template_code,
                "payload": _json_canonical(payload),
                "dedupe_key": dedupe_key,
            },
        )

    # -------------------------
    # Participant checks
    # -------------------------
    def _is_participant(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        request_id: UUID,
        user_id: UUID,
        created_by_user_id: UUID | None,
        subject_employee_id: UUID | None,
        is_admin: bool,
    ) -> bool:
        if is_admin:
            return True
        if created_by_user_id is not None and created_by_user_id == user_id:
            return True

        if subject_employee_id is not None:
            row = db.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM hr_core.employee_user_links
                    WHERE employee_id = :employee_id
                      AND user_id = :user_id
                    """
                ),
                {"employee_id": subject_employee_id, "user_id": user_id},
            ).first()
            if row is not None:
                return True

        row2 = db.execute(
            sa.text(
                """
                SELECT 1
                FROM workflow.request_step_assignees rsa
                JOIN workflow.request_steps s ON s.id = rsa.step_id
                WHERE rsa.tenant_id = :tenant_id
                  AND rsa.user_id = :user_id
                  AND s.request_id = :request_id
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id, "user_id": user_id, "request_id": request_id},
        ).first()
        return row2 is not None

    # -------------------------
    # Requests
    # -------------------------
    def create_request(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        request_type_code: str,
        payload: dict[str, Any],
        subject_employee_id: UUID | None,
        entity_type: str | None,
        entity_id: UUID | None,
        company_id_hint: UUID | None,
        branch_id_hint: UUID | None,
        idempotency_key: str | None,
        initial_comment: str | None,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        company_id = ctx.scope.company_id
        branch_id = ctx.scope.branch_id

        if company_id is None:
            raise AppError(code="iam.scope.invalid_company", message="Company scope is required", status_code=400)

        if company_id_hint is not None and company_id_hint != company_id:
            raise AppError(code="iam.scope.mismatch", message="company_id does not match active scope", status_code=400)
        if branch_id_hint is not None and branch_id_hint != branch_id:
            raise AppError(code="iam.scope.mismatch", message="branch_id does not match active scope", status_code=400)

        # Validate subject employee (if provided) belongs to the active tenant.
        if subject_employee_id is not None:
            ok_emp = db.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM hr_core.employees
                    WHERE id = :id
                      AND tenant_id = :tenant_id
                    """
                ),
                {"id": subject_employee_id, "tenant_id": tenant_id},
            ).first()
            if ok_emp is None:
                raise AppError(code="workflow.request.forbidden", message="Invalid subject_employee_id", status_code=400)

        rt = self._get_request_type(db, request_type_code=request_type_code)
        definition_id = self._get_active_definition_id(
            db, tenant_id=tenant_id, company_id=company_id, request_type_id=rt["id"]
        )
        def_steps = self._load_definition_steps(db, definition_id=definition_id)
        if not def_steps:
            raise AppError(code="workflow.definition.not_found", message="Workflow definition has no steps", status_code=400)

        requester_employee_id = self._resolve_requester_employee_id(db, user_id=ctx.user_id)
        if requester_employee_id is None:
            raise AppError(
                code="workflow.manager_missing",
                message="Requester is not linked to an employee",
                status_code=400,
            )

        # Idempotency: same tenant + caller + key -> same request, unless payload differs.
        if idempotency_key:
            existing = db.execute(
                sa.text(
                    """
                    SELECT
                      r.id,
                      rt.code AS request_type_code,
                      r.company_id,
                      r.branch_id,
                      r.subject_employee_id,
                      r.entity_type,
                      r.entity_id,
                      r.payload,
                      r.status,
                      r.current_step,
                      r.subject,
                      r.created_at,
                      r.updated_at,
                      r.tenant_id,
                      r.created_by_user_id,
                      r.requester_employee_id
                    FROM workflow.requests r
                    JOIN workflow.request_types rt ON rt.id = r.request_type_id
                    WHERE r.tenant_id = :tenant_id
                      AND r.created_by_user_id = :user_id
                      AND r.idempotency_key = :key
                    ORDER BY r.created_at DESC, r.id DESC
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id, "user_id": ctx.user_id, "key": idempotency_key},
            ).mappings().first()
            if existing is not None:
                same = True
                same = same and str(existing["request_type_code"]) == request_type_code
                same = same and UUID(str(existing["company_id"])) == company_id
                same = same and (
                    (existing["branch_id"] is None and branch_id is None)
                    or (existing["branch_id"] is not None and branch_id is not None and UUID(str(existing["branch_id"])) == branch_id)
                )
                same = same and (
                    (existing["subject_employee_id"] is None and subject_employee_id is None)
                    or (
                        existing["subject_employee_id"] is not None
                        and subject_employee_id is not None
                        and UUID(str(existing["subject_employee_id"])) == subject_employee_id
                    )
                )
                same = same and (existing["entity_type"] == entity_type)
                same = same and (
                    (existing["entity_id"] is None and entity_id is None)
                    or (
                        existing["entity_id"] is not None
                        and entity_id is not None
                        and UUID(str(existing["entity_id"])) == entity_id
                    )
                )
                same = same and _json_canonical(existing["payload"] or {}) == _json_canonical(payload or {})

                if not same:
                    raise AppError(
                        code="workflow.idempotency.conflict",
                        message="Idempotency key already used with different payload",
                        status_code=409,
                    )

                # Return the existing request summary without emitting notifications again.
                return dict(existing)

        step_orders = [int(s["step_order"]) for s in def_steps]
        first_step_order = min(step_orders)

        request_id = uuid4()
        subject = payload.get("subject") if isinstance(payload.get("subject"), str) else None

        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO workflow.requests (
                      id,
                      tenant_id,
                      company_id,
                      branch_id,
                      request_type_id,
                      workflow_definition_id,
                      requester_employee_id,
                      subject,
                      status,
                      current_step,
                      payload,
                      created_by_user_id,
                      subject_employee_id,
                      entity_type,
                      entity_id,
                      idempotency_key
                    ) VALUES (
                      :id,
                      :tenant_id,
                      :company_id,
                      :branch_id,
                      :request_type_id,
                      :workflow_definition_id,
                      :requester_employee_id,
                      :subject,
                      'submitted',
                      :current_step,
                      CAST(:payload AS jsonb),
                      :created_by_user_id,
                      :subject_employee_id,
                      :entity_type,
                      :entity_id,
                      :idempotency_key
                    )
                    """
                ),
                {
                    "id": request_id,
                    "tenant_id": tenant_id,
                    "company_id": company_id,
                    "branch_id": branch_id,
                    "request_type_id": rt["id"],
                    "workflow_definition_id": definition_id,
                    "requester_employee_id": requester_employee_id,
                    "subject": subject,
                    "current_step": int(first_step_order),
                    "payload": _json_canonical(payload or {}),
                    "created_by_user_id": ctx.user_id,
                    "subject_employee_id": subject_employee_id,
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "idempotency_key": idempotency_key,
                },
            )
        except IntegrityError as e:
            # Race on idempotency unique index: return existing or conflict.
            db.rollback()
            if idempotency_key:
                existing = db.execute(
                    sa.text(
                        """
                        SELECT
                          r.id,
                          rt.code AS request_type_code,
                          r.company_id,
                          r.branch_id,
                          r.subject_employee_id,
                          r.entity_type,
                          r.entity_id,
                          r.payload,
                          r.status,
                          r.current_step,
                          r.subject,
                          r.created_at,
                          r.updated_at,
                          r.tenant_id,
                          r.created_by_user_id,
                          r.requester_employee_id
                        FROM workflow.requests r
                        JOIN workflow.request_types rt ON rt.id = r.request_type_id
                        WHERE r.tenant_id = :tenant_id
                          AND r.created_by_user_id = :user_id
                          AND r.idempotency_key = :key
                        ORDER BY r.created_at DESC, r.id DESC
                        LIMIT 1
                        """
                    ),
                    {"tenant_id": tenant_id, "user_id": ctx.user_id, "key": idempotency_key},
                ).mappings().first()
                if existing is not None and _json_canonical(existing["payload"] or {}) == _json_canonical(payload or {}):
                    return dict(existing)
            raise AppError(
                code="workflow.idempotency.conflict",
                message="Idempotency key already used",
                status_code=409,
            ) from e

        # Create resolved steps + assignees.
        step_id_by_order: dict[int, UUID] = {}
        first_assignee_user_ids: list[UUID] = []

        for s in def_steps:
            step_order = int(s["step_order"])
            mode = str(s["approver_mode"])
            role_code = s.get("role_code")
            user_id = s.get("user_id")
            fallback_role_code = s.get("fallback_role_code")

            assignee_type: str
            assignee_role_code: str | None = None
            assignee_user_id: UUID | None = None
            resolved_user_ids: list[UUID]

            if mode == "MANAGER":
                mgr_user = self._resolve_manager_user_id(db, tenant_id=tenant_id, employee_id=requester_employee_id)
                if mgr_user is not None:
                    assignee_type = "MANAGER"
                    assignee_user_id = mgr_user
                    resolved_user_ids = [mgr_user]
                else:
                    if fallback_role_code:
                        assignee_type = "ROLE"
                        assignee_role_code = str(fallback_role_code)
                        resolved_user_ids = self._resolve_role_user_ids(
                            db,
                            tenant_id=tenant_id,
                            company_id=company_id,
                            branch_id=branch_id,
                            role_code=assignee_role_code,
                        )
                        if not resolved_user_ids:
                            raise AppError(
                                code="workflow.no_assignees",
                                message="No assignees resolved for fallback role",
                                status_code=400,
                            )
                    else:
                        raise AppError(
                            code="workflow.manager_missing",
                            message="Requester has no manager configured",
                            status_code=400,
                        )
            elif mode == "ROLE":
                if not role_code:
                    raise AppError(code="workflow.definition.not_found", message="ROLE step missing role_code", status_code=400)
                assignee_type = "ROLE"
                assignee_role_code = str(role_code)
                resolved_user_ids = self._resolve_role_user_ids(
                    db,
                    tenant_id=tenant_id,
                    company_id=company_id,
                    branch_id=branch_id,
                    role_code=assignee_role_code,
                )
                if not resolved_user_ids:
                    raise AppError(code="workflow.no_assignees", message="No assignees resolved for role", status_code=400)
            elif mode == "USER":
                if not user_id:
                    raise AppError(code="workflow.definition.not_found", message="USER step missing user_id", status_code=400)
                assignee_type = "USER"
                assignee_user_id = UUID(str(user_id))
                resolved_user_ids = [assignee_user_id]
            else:
                raise AppError(code="workflow.definition.not_found", message=f"Unknown step mode: {mode!r}", status_code=400)

            step_row = db.execute(
                sa.text(
                    """
                    INSERT INTO workflow.request_steps (
                      request_id,
                      step_order,
                      approver_user_id,
                      decision,
                      decided_at,
                      comment,
                      assignee_type,
                      assignee_role_code,
                      assignee_user_id
                    ) VALUES (
                      :request_id,
                      :step_order,
                      :approver_user_id,
                      NULL,
                      NULL,
                      NULL,
                      :assignee_type,
                      :assignee_role_code,
                      :assignee_user_id
                    )
                    RETURNING id
                    """
                ),
                {
                    "request_id": request_id,
                    "step_order": step_order,
                    "approver_user_id": assignee_user_id if assignee_type in ("MANAGER", "USER") else None,
                    "assignee_type": assignee_type,
                    "assignee_role_code": assignee_role_code,
                    "assignee_user_id": assignee_user_id,
                },
            ).first()
            step_id = UUID(str(step_row[0]))
            step_id_by_order[step_order] = step_id

            for uid in resolved_user_ids:
                db.execute(
                    sa.text(
                        """
                        INSERT INTO workflow.request_step_assignees (tenant_id, step_id, user_id)
                        VALUES (:tenant_id, :step_id, :user_id)
                        ON CONFLICT DO NOTHING
                        """
                    ),
                    {"tenant_id": tenant_id, "step_id": step_id, "user_id": uid},
                )

            if step_order == first_step_order:
                first_assignee_user_ids = resolved_user_ids

        # Optional initial comment
        if initial_comment:
            db.execute(
                sa.text(
                    """
                    INSERT INTO workflow.request_comments (request_id, author_user_id, body)
                    VALUES (:request_id, :user_id, :body)
                    """
                ),
                {"request_id": request_id, "user_id": ctx.user_id, "body": initial_comment},
            )
            self._insert_event(
                db,
                tenant_id=tenant_id,
                request_id=request_id,
                actor_user_id=ctx.user_id,
                event_type="COMMENT_ADDED",
                data={"source": "create"},
                correlation_id=ctx.correlation_id,
            )

        # Events + notifications for the first step
        self._insert_event(
            db,
            tenant_id=tenant_id,
            request_id=request_id,
            actor_user_id=ctx.user_id,
            event_type="REQUEST_CREATED",
            data={"request_type_code": request_type_code},
            correlation_id=ctx.correlation_id,
        )
        self._insert_event(
            db,
            tenant_id=tenant_id,
            request_id=request_id,
            actor_user_id=ctx.user_id,
            event_type="STEP_ASSIGNED",
            data={"step_order": first_step_order, "assignee_user_ids": [str(u) for u in first_assignee_user_ids]},
            correlation_id=ctx.correlation_id,
        )

        for uid in first_assignee_user_ids:
            self._enqueue_in_app_notification(
                db,
                tenant_id=tenant_id,
                recipient_user_id=uid,
                template_code="workflow.step.assigned",
                dedupe_key=f"workflow:workflow.step.assigned:{request_id}:{first_step_order}:{uid}",
                payload={
                    "title": "Approval required",
                    "body": f"New {request_type_code} request is awaiting your approval",
                    "entity_type": "workflow.request",
                    "entity_id": str(request_id),
                    "action_url": f"/workflow/requests/{request_id}",
                    "correlation_id": ctx.correlation_id,
                },
            )

        audit_svc.record(
            db,
            ctx=ctx,
            action="workflow.request.create",
            entity_type="workflow.request",
            entity_id=request_id,
            before=None,
            after={
                "request_type_code": request_type_code,
                "status": "submitted",
                "current_step": first_step_order,
                "company_id": str(company_id),
                "branch_id": str(branch_id) if branch_id is not None else None,
                "entity_type": entity_type,
                "entity_id": str(entity_id) if entity_id is not None else None,
                "idempotency_key": idempotency_key,
                "payload_keys": sorted(list(payload.keys()))[:50],
            },
        )

        db.commit()

        return {
            "id": request_id,
            "request_type_code": request_type_code,
            "status": "submitted",
            "current_step": first_step_order,
            "subject": subject,
            "payload": payload,
            "tenant_id": tenant_id,
            "company_id": company_id,
            "branch_id": branch_id,
            "created_by_user_id": ctx.user_id,
            "requester_employee_id": requester_employee_id,
            "subject_employee_id": subject_employee_id,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "created_at": _utcnow(),  # best-effort (API callers typically refetch)
            "updated_at": _utcnow(),
        }

    def get_request_detail(self, db: Session, *, ctx: AuthContext, request_id: UUID) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        is_admin = "workflow:request:admin" in ctx.permissions

        req = db.execute(
            sa.text(
                """
                SELECT
                  r.id,
                  rt.code AS request_type_code,
                  r.tenant_id,
                  r.company_id,
                  r.branch_id,
                  r.workflow_definition_id,
                  r.requester_employee_id,
                  r.created_by_user_id,
                  r.subject_employee_id,
                  r.entity_type,
                  r.entity_id,
                  r.subject,
                  r.status,
                  r.current_step,
                  r.payload,
                  r.created_at,
                  r.updated_at
                FROM workflow.requests r
                JOIN workflow.request_types rt ON rt.id = r.request_type_id
                WHERE r.id = :id
                  AND r.tenant_id = :tenant_id
                """
            ),
            {"id": request_id, "tenant_id": tenant_id},
        ).mappings().first()
        if req is None:
            raise AppError(code="workflow.request.not_found", message="Request not found", status_code=404)

        if not self._is_participant(
            db,
            tenant_id=tenant_id,
            request_id=request_id,
            user_id=ctx.user_id,
            created_by_user_id=req.get("created_by_user_id"),
            subject_employee_id=req.get("subject_employee_id"),
            is_admin=is_admin,
        ):
            raise AppError(code="workflow.request.not_participant", message="Request not found", status_code=404)

        steps = db.execute(
            sa.text(
                """
                SELECT
                  id,
                  step_order,
                  assignee_type,
                  assignee_role_code,
                  assignee_user_id,
                  decision,
                  decided_at,
                  approver_user_id,
                  comment,
                  created_at
                FROM workflow.request_steps
                WHERE request_id = :request_id
                ORDER BY step_order ASC
                """
            ),
            {"request_id": request_id},
        ).mappings().all()

        assignees = db.execute(
            sa.text(
                """
                SELECT rsa.step_id, rsa.user_id
                FROM workflow.request_step_assignees rsa
                JOIN workflow.request_steps s ON s.id = rsa.step_id
                WHERE rsa.tenant_id = :tenant_id
                  AND s.request_id = :request_id
                """
            ),
            {"tenant_id": tenant_id, "request_id": request_id},
        ).all()
        assignees_by_step: dict[UUID, list[UUID]] = {}
        for step_id_raw, user_id_raw in assignees:
            sid = UUID(str(step_id_raw))
            assignees_by_step.setdefault(sid, []).append(UUID(str(user_id_raw)))

        comments = db.execute(
            sa.text(
                """
                SELECT id, author_user_id, body, created_at
                FROM workflow.request_comments
                WHERE request_id = :request_id
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"request_id": request_id},
        ).mappings().all()

        attachments = db.execute(
            sa.text(
                """
                SELECT id, file_id, created_by, note, created_at
                FROM workflow.request_attachments
                WHERE tenant_id = :tenant_id
                  AND request_id = :request_id
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"tenant_id": tenant_id, "request_id": request_id},
        ).mappings().all()

        events = db.execute(
            sa.text(
                """
                SELECT id, actor_user_id, event_type, data, correlation_id, created_at
                FROM workflow.request_events
                WHERE tenant_id = :tenant_id
                  AND request_id = :request_id
                ORDER BY created_at ASC, id ASC
                """
            ),
            {"tenant_id": tenant_id, "request_id": request_id},
        ).mappings().all()

        return {
            "request": dict(req),
            "steps": [dict(s) for s in steps],
            "assignees_by_step": assignees_by_step,
            "comments": [dict(c) for c in comments],
            "attachments": [dict(a) for a in attachments],
            "events": [dict(e) for e in events],
        }

    def list_inbox(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        request_type_code: str | None,
        company_id: UUID | None,
        branch_id: UUID | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id
        cursor_ts = cursor[0] if cursor else None
        cursor_id = cursor[1] if cursor else None

        rows = db.execute(
            sa.text(
                """
                SELECT
                  r.id,
                  rt.code AS request_type_code,
                  r.tenant_id,
                  r.company_id,
                  r.branch_id,
                  r.requester_employee_id,
                  r.created_by_user_id,
                  r.subject_employee_id,
                  r.entity_type,
                  r.entity_id,
                  r.subject,
                  r.status,
                  r.current_step,
                  r.created_at,
                  r.updated_at
                FROM workflow.requests r
                JOIN workflow.request_types rt ON rt.id = r.request_type_id
                JOIN workflow.request_steps s
                  ON s.request_id = r.id
                 AND s.step_order = r.current_step
                JOIN workflow.request_step_assignees rsa
                  ON rsa.step_id = s.id
                 AND rsa.user_id = :user_id
                 AND rsa.tenant_id = :tenant_id
                WHERE r.tenant_id = :tenant_id
                  AND r.status = 'submitted'
                  AND s.decision IS NULL
                  AND (CAST(:request_type_code AS text) IS NULL OR rt.code = :request_type_code)
                  AND (CAST(:company_id AS uuid) IS NULL OR r.company_id = :company_id)
                  AND (CAST(:branch_id AS uuid) IS NULL OR r.branch_id = :branch_id)
                  AND (
                    CAST(:cursor_ts AS timestamptz) IS NULL
                    OR (r.created_at, r.id) < (CAST(:cursor_ts AS timestamptz), CAST(:cursor_id AS uuid))
                  )
                ORDER BY r.created_at DESC, r.id DESC
                LIMIT :limit
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": ctx.user_id,
                "request_type_code": request_type_code,
                "company_id": company_id,
                "branch_id": branch_id,
                "cursor_ts": cursor_ts,
                "cursor_id": cursor_id,
                "limit": int(limit),
            },
        ).mappings().all()
        return [dict(r) for r in rows]

    def list_outbox(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        status: str | None,
        request_type_code: str | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id
        cursor_ts = cursor[0] if cursor else None
        cursor_id = cursor[1] if cursor else None
        db_status = api_to_db_status(status) if status else None

        rows = db.execute(
            sa.text(
                """
                SELECT
                  r.id,
                  rt.code AS request_type_code,
                  r.tenant_id,
                  r.company_id,
                  r.branch_id,
                  r.requester_employee_id,
                  r.created_by_user_id,
                  r.subject_employee_id,
                  r.entity_type,
                  r.entity_id,
                  r.subject,
                  r.status,
                  r.current_step,
                  r.created_at,
                  r.updated_at
                FROM workflow.requests r
                JOIN workflow.request_types rt ON rt.id = r.request_type_id
                WHERE r.tenant_id = :tenant_id
                  AND r.created_by_user_id = :user_id
                  AND (CAST(:status AS text) IS NULL OR r.status = :status)
                  AND (CAST(:request_type_code AS text) IS NULL OR rt.code = :request_type_code)
                  AND (
                    CAST(:cursor_ts AS timestamptz) IS NULL
                    OR (r.created_at, r.id) < (CAST(:cursor_ts AS timestamptz), CAST(:cursor_id AS uuid))
                  )
                ORDER BY r.created_at DESC, r.id DESC
                LIMIT :limit
                """
            ),
            {
                "tenant_id": tenant_id,
                "user_id": ctx.user_id,
                "status": db_status,
                "request_type_code": request_type_code,
                "cursor_ts": cursor_ts,
                "cursor_id": cursor_id,
                "limit": int(limit),
            },
        ).mappings().all()
        return [dict(r) for r in rows]

    # -------------------------
    # Actions
    # -------------------------
    def _require_current_step_assignee(
        self, db: Session, *, tenant_id: UUID, step_id: UUID, user_id: UUID
    ) -> None:
        row = db.execute(
            sa.text(
                """
                SELECT 1
                FROM workflow.request_step_assignees
                WHERE tenant_id = :tenant_id
                  AND step_id = :step_id
                  AND user_id = :user_id
                """
            ),
            {"tenant_id": tenant_id, "step_id": step_id, "user_id": user_id},
        ).first()
        if row is None:
            raise AppError(code="workflow.step.not_assignee", message="Not an assignee of the current step", status_code=403)

    def approve_request(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        request_id: UUID,
        comment: str | None,
    ) -> dict[str, Any]:
        return self._decide(db, ctx=ctx, request_id=request_id, decision="approved", comment=comment)

    def reject_request(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        request_id: UUID,
        comment: str,
    ) -> dict[str, Any]:
        return self._decide(db, ctx=ctx, request_id=request_id, decision="rejected", comment=comment)

    def _decide(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        request_id: UUID,
        decision: str,
        comment: str | None,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        now = _utcnow()

        # Lock request row first (concurrency safety).
        req = db.execute(
            sa.text(
                """
                SELECT
                  r.id,
                  r.status,
                  r.current_step,
                  r.company_id,
                  r.branch_id,
                  r.created_by_user_id,
                  rt.code AS request_type_code
                FROM workflow.requests r
                JOIN workflow.request_types rt ON rt.id = r.request_type_id
                WHERE r.id = :id
                  AND r.tenant_id = :tenant_id
                FOR UPDATE
                """
            ),
            {"id": request_id, "tenant_id": tenant_id},
        ).mappings().first()
        if req is None:
            raise AppError(code="workflow.request.not_found", message="Request not found", status_code=404)

        current_step = int(req["current_step"])

        step = db.execute(
            sa.text(
                """
                SELECT id, decision
                FROM workflow.request_steps
                WHERE request_id = :request_id
                  AND step_order = :step_order
                FOR UPDATE
                """
            ),
            {"request_id": request_id, "step_order": current_step},
        ).mappings().first()
        if step is None:
            raise AppError(code="workflow.step.not_pending", message="Current step not found", status_code=409)

        if step["decision"] is not None:
            raise AppError(code="workflow.step.already_decided", message="Step already decided", status_code=409)
        if str(req["status"]) != "submitted":
            raise AppError(code="workflow.request.not_pending", message="Request is not pending", status_code=409)

        step_id = UUID(str(step["id"]))
        self._require_current_step_assignee(db, tenant_id=tenant_id, step_id=step_id, user_id=ctx.user_id)

        # Decide current step.
        db.execute(
            sa.text(
                """
                UPDATE workflow.request_steps
                SET decision = :decision,
                    decided_at = :decided_at,
                    comment = :comment,
                    approver_user_id = :actor_user_id
                WHERE id = :id
                """
            ),
            {
                "decision": decision,
                "decided_at": now,
                "comment": comment,
                "actor_user_id": ctx.user_id,
                "id": step_id,
            },
        )

        self._insert_event(
            db,
            tenant_id=tenant_id,
            request_id=request_id,
            actor_user_id=ctx.user_id,
            event_type="STEP_APPROVED" if decision == "approved" else "STEP_REJECTED",
            data={"step_order": current_step},
            correlation_id=ctx.correlation_id,
        )

        before = {"status": str(req["status"]), "current_step": current_step}

        if decision == "approved":
            next_step = db.execute(
                sa.text(
                    """
                    SELECT id, step_order
                    FROM workflow.request_steps
                    WHERE request_id = :request_id
                      AND step_order > :current_step
                    ORDER BY step_order ASC
                    LIMIT 1
                    """
                ),
                {"request_id": request_id, "current_step": current_step},
            ).mappings().first()

            if next_step is not None:
                next_step_id = UUID(str(next_step["id"]))
                next_step_order = int(next_step["step_order"])

                db.execute(
                    sa.text(
                        """
                        UPDATE workflow.requests
                        SET current_step = :next_step,
                            updated_at = now()
                        WHERE id = :id
                          AND tenant_id = :tenant_id
                        """
                    ),
                    {"id": request_id, "tenant_id": tenant_id, "next_step": next_step_order},
                )

                self._insert_event(
                    db,
                    tenant_id=tenant_id,
                    request_id=request_id,
                    actor_user_id=ctx.user_id,
                    event_type="STEP_ASSIGNED",
                    data={"step_order": next_step_order},
                    correlation_id=ctx.correlation_id,
                )

                assignee_rows = db.execute(
                    sa.text(
                        """
                        SELECT user_id
                        FROM workflow.request_step_assignees
                        WHERE tenant_id = :tenant_id
                          AND step_id = :step_id
                        ORDER BY user_id
                        """
                    ),
                    {"tenant_id": tenant_id, "step_id": next_step_id},
                ).all()
                next_assignees = [UUID(str(r[0])) for r in assignee_rows]

                for uid in next_assignees:
                    self._enqueue_in_app_notification(
                        db,
                        tenant_id=tenant_id,
                        recipient_user_id=uid,
                        template_code="workflow.step.assigned",
                        dedupe_key=f"workflow:workflow.step.assigned:{request_id}:{next_step_order}:{uid}",
                        payload={
                            "title": "Approval required",
                            "body": f"Request {req['request_type_code']} is awaiting your approval",
                            "entity_type": "workflow.request",
                            "entity_id": str(request_id),
                            "action_url": f"/workflow/requests/{request_id}",
                            "correlation_id": ctx.correlation_id,
                        },
                    )

                after = {"status": "submitted", "current_step": next_step_order}
                audit_svc.record(
                    db,
                    ctx=ctx,
                    action="workflow.request.approve",
                    entity_type="workflow.request",
                    entity_id=request_id,
                    before=before,
                    after=after,
                )
                db.commit()
                return {"id": str(request_id), "status": db_to_api_status("submitted"), "current_step": next_step_order}

            # Finalize approved
            db.execute(
                sa.text(
                    """
                    UPDATE workflow.requests
                    SET status = 'approved',
                        updated_at = now()
                    WHERE id = :id
                      AND tenant_id = :tenant_id
                    """
                ),
                {"id": request_id, "tenant_id": tenant_id},
            )
            self._insert_event(
                db,
                tenant_id=tenant_id,
                request_id=request_id,
                actor_user_id=ctx.user_id,
                event_type="REQUEST_APPROVED",
                data={},
                correlation_id=ctx.correlation_id,
            )

            requester_user_id = req.get("created_by_user_id")
            if requester_user_id is not None:
                ruid = UUID(str(requester_user_id))
                self._enqueue_in_app_notification(
                    db,
                    tenant_id=tenant_id,
                    recipient_user_id=ruid,
                    template_code="workflow.request.finalized",
                    dedupe_key=f"workflow:workflow.request.finalized:{request_id}:approved:{ruid}",
                    payload={
                        "title": "Request approved",
                        "body": f"Your {req['request_type_code']} request was approved",
                        "entity_type": "workflow.request",
                        "entity_id": str(request_id),
                        "action_url": f"/workflow/requests/{request_id}",
                        "correlation_id": ctx.correlation_id,
                    },
                )

            after = {"status": "approved", "current_step": current_step}
            audit_svc.record(
                db,
                ctx=ctx,
                action="workflow.request.approve",
                entity_type="workflow.request",
                entity_id=request_id,
                before=before,
                after=after,
            )
            db.commit()
            return {"id": str(request_id), "status": db_to_api_status("approved"), "current_step": current_step}

        # Reject: finalize rejected
        db.execute(
            sa.text(
                """
                UPDATE workflow.requests
                SET status = 'rejected',
                    updated_at = now()
                WHERE id = :id
                  AND tenant_id = :tenant_id
                """
            ),
            {"id": request_id, "tenant_id": tenant_id},
        )
        self._insert_event(
            db,
            tenant_id=tenant_id,
            request_id=request_id,
            actor_user_id=ctx.user_id,
            event_type="REQUEST_REJECTED",
            data={},
            correlation_id=ctx.correlation_id,
        )

        requester_user_id = req.get("created_by_user_id")
        if requester_user_id is not None:
            ruid = UUID(str(requester_user_id))
            self._enqueue_in_app_notification(
                db,
                tenant_id=tenant_id,
                recipient_user_id=ruid,
                template_code="workflow.request.finalized",
                dedupe_key=f"workflow:workflow.request.finalized:{request_id}:rejected:{ruid}",
                payload={
                    "title": "Request rejected",
                    "body": f"Your {req['request_type_code']} request was rejected",
                    "entity_type": "workflow.request",
                    "entity_id": str(request_id),
                    "action_url": f"/workflow/requests/{request_id}",
                    "correlation_id": ctx.correlation_id,
                },
            )

        after = {"status": "rejected", "current_step": current_step}
        audit_svc.record(
            db,
            ctx=ctx,
            action="workflow.request.reject",
            entity_type="workflow.request",
            entity_id=request_id,
            before=before,
            after=after,
        )
        db.commit()
        return {"id": str(request_id), "status": db_to_api_status("rejected"), "current_step": current_step}

    def cancel_request(self, db: Session, *, ctx: AuthContext, request_id: UUID) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        now = _utcnow()

        req = db.execute(
            sa.text(
                """
                SELECT
                  r.id,
                  r.status,
                  r.current_step,
                  r.created_by_user_id,
                  rt.code AS request_type_code
                FROM workflow.requests r
                JOIN workflow.request_types rt ON rt.id = r.request_type_id
                WHERE r.id = :id
                  AND r.tenant_id = :tenant_id
                FOR UPDATE
                """
            ),
            {"id": request_id, "tenant_id": tenant_id},
        ).mappings().first()
        if req is None:
            raise AppError(code="workflow.request.not_found", message="Request not found", status_code=404)

        is_admin = "workflow:request:admin" in ctx.permissions
        created_by_user_id = UUID(str(req["created_by_user_id"])) if req.get("created_by_user_id") else None
        if not is_admin and created_by_user_id != ctx.user_id:
            # If the user can't cancel, hide existence unless they are a participant.
            if not self._is_participant(
                db,
                tenant_id=tenant_id,
                request_id=request_id,
                user_id=ctx.user_id,
                created_by_user_id=req.get("created_by_user_id"),
                subject_employee_id=None,
                is_admin=is_admin,
            ):
                raise AppError(code="workflow.request.not_participant", message="Request not found", status_code=404)
            raise AppError(code="workflow.request.forbidden", message="Only requester can cancel", status_code=403)

        if str(req["status"]) != "submitted":
            raise AppError(code="workflow.request.not_pending", message="Request is not pending", status_code=409)

        current_step = int(req["current_step"])
        step = db.execute(
            sa.text(
                """
                SELECT id
                FROM workflow.request_steps
                WHERE request_id = :request_id
                  AND step_order = :step_order
                LIMIT 1
                """
            ),
            {"request_id": request_id, "step_order": current_step},
        ).mappings().first()
        step_id = UUID(str(step["id"])) if step is not None else None

        db.execute(
            sa.text(
                """
                UPDATE workflow.requests
                SET status = 'cancelled',
                    updated_at = now()
                WHERE id = :id
                  AND tenant_id = :tenant_id
                """
            ),
            {"id": request_id, "tenant_id": tenant_id},
        )

        self._insert_event(
            db,
            tenant_id=tenant_id,
            request_id=request_id,
            actor_user_id=ctx.user_id,
            event_type="REQUEST_CANCELLED",
            data={},
            correlation_id=ctx.correlation_id,
        )

        # Notify current assignees (best-effort).
        if step_id is not None:
            assignees = db.execute(
                sa.text(
                    """
                    SELECT user_id
                    FROM workflow.request_step_assignees
                    WHERE tenant_id = :tenant_id
                      AND step_id = :step_id
                    """
                ),
                {"tenant_id": tenant_id, "step_id": step_id},
            ).all()
            for (uid_raw,) in assignees:
                uid = UUID(str(uid_raw))
                self._enqueue_in_app_notification(
                    db,
                    tenant_id=tenant_id,
                    recipient_user_id=uid,
                    template_code="workflow.request.finalized",
                    dedupe_key=f"workflow:workflow.request.finalized:{request_id}:cancelled:{uid}",
                    payload={
                        "title": "Request cancelled",
                        "body": f"Request {req['request_type_code']} was cancelled",
                        "entity_type": "workflow.request",
                        "entity_id": str(request_id),
                        "action_url": f"/workflow/requests/{request_id}",
                        "correlation_id": ctx.correlation_id,
                    },
                )

        audit_svc.record(
            db,
            ctx=ctx,
            action="workflow.request.cancel",
            entity_type="workflow.request",
            entity_id=request_id,
            before={"status": "submitted", "current_step": current_step},
            after={"status": "cancelled", "current_step": current_step},
        )

        db.commit()
        return {"id": str(request_id), "status": db_to_api_status("cancelled"), "cancelled_at": now.isoformat()}

    # -------------------------
    # Comments / Attachments
    # -------------------------
    def add_comment(self, db: Session, *, ctx: AuthContext, request_id: UUID, body: str) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        is_admin = "workflow:request:admin" in ctx.permissions

        req = db.execute(
            sa.text(
                """
                SELECT
                  r.id,
                  r.current_step,
                  r.created_by_user_id,
                  r.subject_employee_id,
                  rt.code AS request_type_code
                FROM workflow.requests r
                JOIN workflow.request_types rt ON rt.id = r.request_type_id
                WHERE r.id = :id
                  AND r.tenant_id = :tenant_id
                """
            ),
            {"id": request_id, "tenant_id": tenant_id},
        ).mappings().first()
        if req is None:
            raise AppError(code="workflow.request.not_found", message="Request not found", status_code=404)

        if not self._is_participant(
            db,
            tenant_id=tenant_id,
            request_id=request_id,
            user_id=ctx.user_id,
            created_by_user_id=req.get("created_by_user_id"),
            subject_employee_id=req.get("subject_employee_id"),
            is_admin=is_admin,
        ):
            raise AppError(code="workflow.request.not_participant", message="Request not found", status_code=404)

        row = db.execute(
            sa.text(
                """
                INSERT INTO workflow.request_comments (request_id, author_user_id, body)
                VALUES (:request_id, :author_user_id, :body)
                RETURNING id, created_at
                """
            ),
            {"request_id": request_id, "author_user_id": ctx.user_id, "body": body},
        ).mappings().first()
        comment_id = UUID(str(row["id"]))
        created_at = row["created_at"]

        self._insert_event(
            db,
            tenant_id=tenant_id,
            request_id=request_id,
            actor_user_id=ctx.user_id,
            event_type="COMMENT_ADDED",
            data={"comment_id": str(comment_id)},
            correlation_id=ctx.correlation_id,
        )

        # Notify the "other side" (minimal v1 behavior).
        recipients: list[UUID] = []
        requester_user_id = req.get("created_by_user_id")
        current_step = int(req["current_step"])
        if requester_user_id is not None and UUID(str(requester_user_id)) == ctx.user_id:
            # Requester commented: notify current step assignees.
            step = db.execute(
                sa.text(
                    """
                    SELECT id
                    FROM workflow.request_steps
                    WHERE request_id = :request_id
                      AND step_order = :step_order
                    LIMIT 1
                    """
                ),
                {"request_id": request_id, "step_order": current_step},
            ).mappings().first()
            if step is not None:
                step_id = UUID(str(step["id"]))
                rows = db.execute(
                    sa.text(
                        """
                        SELECT user_id
                        FROM workflow.request_step_assignees
                        WHERE tenant_id = :tenant_id
                          AND step_id = :step_id
                          AND user_id <> :actor_user_id
                        """
                    ),
                    {"tenant_id": tenant_id, "step_id": step_id, "actor_user_id": ctx.user_id},
                ).all()
                recipients = [UUID(str(r[0])) for r in rows]
        else:
            # Approver/commenter: notify requester.
            if requester_user_id is not None:
                ruid = UUID(str(requester_user_id))
                if ruid != ctx.user_id:
                    recipients = [ruid]

        for uid in recipients:
            self._enqueue_in_app_notification(
                db,
                tenant_id=tenant_id,
                recipient_user_id=uid,
                template_code="workflow.comment.added",
                dedupe_key=f"workflow:workflow.comment.added:{request_id}:{comment_id}:{uid}",
                payload={
                    "title": "New comment",
                    "body": f"New comment on request {req['request_type_code']}",
                    "entity_type": "workflow.request",
                    "entity_id": str(request_id),
                    "action_url": f"/workflow/requests/{request_id}",
                    "correlation_id": ctx.correlation_id,
                },
            )

        db.commit()
        return {"id": str(comment_id), "created_at": created_at.isoformat()}

    def add_attachment(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        request_id: UUID,
        file_id: UUID,
        note: str | None,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        is_admin = "workflow:request:admin" in ctx.permissions

        req = db.execute(
            sa.text(
                """
                SELECT id, created_by_user_id, subject_employee_id
                FROM workflow.requests
                WHERE id = :id
                  AND tenant_id = :tenant_id
                """
            ),
            {"id": request_id, "tenant_id": tenant_id},
        ).mappings().first()
        if req is None:
            raise AppError(code="workflow.request.not_found", message="Request not found", status_code=404)

        if not self._is_participant(
            db,
            tenant_id=tenant_id,
            request_id=request_id,
            user_id=ctx.user_id,
            created_by_user_id=req.get("created_by_user_id"),
            subject_employee_id=req.get("subject_employee_id"),
            is_admin=is_admin,
        ):
            raise AppError(code="workflow.request.not_participant", message="Request not found", status_code=404)

        file_ok = db.execute(
            sa.text("SELECT 1 FROM dms.files WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": file_id, "tenant_id": tenant_id},
        ).first()
        if file_ok is None:
            raise AppError(code="workflow.request.forbidden", message="Invalid file_id", status_code=400)

        row = db.execute(
            sa.text(
                """
                INSERT INTO workflow.request_attachments (tenant_id, request_id, file_id, created_by, note)
                VALUES (:tenant_id, :request_id, :file_id, :created_by, :note)
                RETURNING id, created_at
                """
            ),
            {
                "tenant_id": tenant_id,
                "request_id": request_id,
                "file_id": file_id,
                "created_by": ctx.user_id,
                "note": note,
            },
        ).mappings().first()
        attachment_id = UUID(str(row["id"]))
        created_at = row["created_at"]

        self._insert_event(
            db,
            tenant_id=tenant_id,
            request_id=request_id,
            actor_user_id=ctx.user_id,
            event_type="ATTACHMENT_ADDED",
            data={"attachment_id": str(attachment_id), "file_id": str(file_id)},
            correlation_id=ctx.correlation_id,
        )

        db.commit()
        return {"id": str(attachment_id), "created_at": created_at.isoformat()}

    # -------------------------
    # Definitions (admin)
    # -------------------------
    def list_definitions(self, db: Session, *, ctx: AuthContext, company_id: UUID | None) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id

        rows = db.execute(
            sa.text(
                """
                SELECT
                  d.id,
                  d.tenant_id,
                  d.company_id,
                  rt.code AS request_type_code,
                  d.code,
                  d.name,
                  d.version,
                  d.is_active,
                  d.created_by AS created_by_user_id,
                  d.created_at,
                  d.updated_at
                FROM workflow.workflow_definitions d
                JOIN workflow.request_types rt ON rt.id = d.request_type_id
                WHERE d.tenant_id = :tenant_id
                  AND (CAST(:company_id AS uuid) IS NULL OR d.company_id = :company_id)
                ORDER BY d.updated_at DESC, d.id DESC
                """
            ),
            {"tenant_id": tenant_id, "company_id": company_id},
        ).mappings().all()
        defs = [dict(r) for r in rows]
        if not defs:
            return []

        def_ids = [d["id"] for d in defs]
        step_rows = db.execute(
            sa.text(
                """
                SELECT
                  workflow_definition_id,
                  step_order,
                  approver_mode,
                  role_code,
                  user_id,
                  scope_mode,
                  fallback_role_code
                FROM workflow.workflow_definition_steps
                WHERE workflow_definition_id = ANY(:ids)
                ORDER BY workflow_definition_id, step_order ASC
                """
            ),
            {"ids": def_ids},
        ).mappings().all()

        steps_by_def: dict[UUID, list[dict[str, Any]]] = {}
        for s in step_rows:
            did = UUID(str(s["workflow_definition_id"]))
            steps_by_def.setdefault(did, []).append(dict(s))

        for d in defs:
            d["steps"] = steps_by_def.get(UUID(str(d["id"])), [])
        return defs

    def create_definition(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        request_type_code: str,
        code: str,
        name: str,
        version: int,
        company_id: UUID | None,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        rt = self._get_request_type(db, request_type_code=request_type_code)

        definition_id = uuid4()
        db.execute(
            sa.text(
                """
                INSERT INTO workflow.workflow_definitions (
                  id, tenant_id, company_id, request_type_id, name, is_active, created_by, code, version
                ) VALUES (
                  :id, :tenant_id, :company_id, :request_type_id, :name, false, :created_by, :code, :version
                )
                """
            ),
            {
                "id": definition_id,
                "tenant_id": tenant_id,
                "company_id": company_id,
                "request_type_id": rt["id"],
                "name": name,
                "created_by": ctx.user_id,
                "code": code,
                "version": int(version),
            },
        )
        db.commit()
        return {
            "id": definition_id,
            "tenant_id": tenant_id,
            "company_id": company_id,
            "request_type_code": request_type_code,
            "code": code,
            "name": name,
            "version": version,
            "is_active": False,
            "created_by_user_id": ctx.user_id,
            "created_at": _utcnow(),
            "updated_at": _utcnow(),
            "steps": [],
        }

    def replace_definition_steps(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        definition_id: UUID,
        steps: list[dict[str, Any]],
    ) -> None:
        tenant_id = ctx.scope.tenant_id

        # Ensure definition belongs to tenant and get request_type_id for later activation logic.
        row = db.execute(
            sa.text(
                """
                SELECT id
                FROM workflow.workflow_definitions
                WHERE id = :id
                  AND tenant_id = :tenant_id
                """
            ),
            {"id": definition_id, "tenant_id": tenant_id},
        ).first()
        if row is None:
            raise AppError(code="workflow.definition.not_found", message="Definition not found", status_code=404)

        # Replace in a single transaction.
        db.execute(
            sa.text("DELETE FROM workflow.workflow_definition_steps WHERE workflow_definition_id = :id"),
            {"id": definition_id},
        )

        for s in steps:
            step_order = int(s["step_index"])
            assignee_type = str(s["assignee_type"])
            role_code = s.get("assignee_role_code")
            user_id = s.get("assignee_user_id")
            scope_mode = s.get("scope_mode") or "TENANT"
            fallback_role_code = s.get("fallback_role_code")

            if assignee_type == "ROLE" and not role_code:
                raise AppError(code="validation_error", message="ROLE steps require assignee_role_code", status_code=400)
            if assignee_type == "USER" and not user_id:
                raise AppError(code="validation_error", message="USER steps require assignee_user_id", status_code=400)

            db.execute(
                sa.text(
                    """
                    INSERT INTO workflow.workflow_definition_steps (
                      workflow_definition_id, step_order, approver_mode, role_code, user_id, scope_mode, fallback_role_code
                    ) VALUES (
                      :workflow_definition_id, :step_order, :approver_mode, :role_code, :user_id, :scope_mode, :fallback_role_code
                    )
                    """
                ),
                {
                    "workflow_definition_id": definition_id,
                    "step_order": step_order,
                    "approver_mode": assignee_type,
                    "role_code": role_code,
                    "user_id": user_id,
                    "scope_mode": scope_mode,
                    "fallback_role_code": fallback_role_code,
                },
            )

        db.commit()

    def activate_definition(self, db: Session, *, ctx: AuthContext, definition_id: UUID) -> None:
        tenant_id = ctx.scope.tenant_id

        d = db.execute(
            sa.text(
                """
                SELECT id, request_type_id, company_id
                FROM workflow.workflow_definitions
                WHERE id = :id
                  AND tenant_id = :tenant_id
                FOR UPDATE
                """
            ),
            {"id": definition_id, "tenant_id": tenant_id},
        ).mappings().first()
        if d is None:
            raise AppError(code="workflow.definition.not_found", message="Definition not found", status_code=404)

        request_type_id = d["request_type_id"]
        company_id = d["company_id"]

        # Deactivate previous active definitions for the same (tenant, request_type, company).
        if company_id is None:
            db.execute(
                sa.text(
                    """
                    UPDATE workflow.workflow_definitions
                    SET is_active = false,
                        updated_at = now()
                    WHERE tenant_id = :tenant_id
                      AND request_type_id = :request_type_id
                      AND company_id IS NULL
                      AND id <> :id
                    """
                ),
                {"tenant_id": tenant_id, "request_type_id": request_type_id, "id": definition_id},
            )
        else:
            db.execute(
                sa.text(
                    """
                    UPDATE workflow.workflow_definitions
                    SET is_active = false,
                        updated_at = now()
                    WHERE tenant_id = :tenant_id
                      AND request_type_id = :request_type_id
                      AND company_id = :company_id
                      AND id <> :id
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "request_type_id": request_type_id,
                    "company_id": company_id,
                    "id": definition_id,
                },
            )

        db.execute(
            sa.text(
                """
                UPDATE workflow.workflow_definitions
                SET is_active = true,
                    updated_at = now()
                WHERE id = :id
                  AND tenant_id = :tenant_id
                """
            ),
            {"id": definition_id, "tenant_id": tenant_id},
        )
        db.commit()
