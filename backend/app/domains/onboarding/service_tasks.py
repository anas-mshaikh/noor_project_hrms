"""
Onboarding v2 ESS task service (Milestone 6).

This module contains employee-facing onboarding operations:
- read own onboarding bundle + tasks
- submit FORM tasks (JSON payload)
- upload DOCUMENT tasks (DMS integration + optional verification workflow)
- ACK tasks (v1 placeholder)
- submit onboarding packet (aggregate FORM submissions into HR_PROFILE_CHANGE)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.dms.service_documents import DmsDocumentService
from app.domains.dms.service_files import DmsFileService
from app.domains.onboarding.utils import (
    enqueue_notification,
    get_actor_employee_or_409,
    json_canonical,
    list_employee_user_ids,
    utcnow,
)
from app.domains.profile_change.service import (
    ProfileChangeService,
    normalize_change_set,
)
from app.shared.types import AuthContext


class OnboardingTaskService:
    """ESS-facing onboarding operations."""

    def __init__(self) -> None:
        self._files = DmsFileService()
        self._docs = DmsDocumentService()
        self._profile_changes = ProfileChangeService()

    def get_my_onboarding(
        self, db: Session, *, ctx: AuthContext
    ) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
        """Return the actor's active bundle + tasks (or None if not started)."""

        actor = get_actor_employee_or_409(db, ctx=ctx)
        tenant_id = actor.tenant_id

        bundle = (
            db.execute(
                sa.text(
                    """
                SELECT *
                FROM onboarding.employee_bundles
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND status = 'ACTIVE'
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """
                ),
                {"tenant_id": tenant_id, "employee_id": actor.employee_id},
            )
            .mappings()
            .first()
        )
        if bundle is None:
            return None, []

        tasks = (
            db.execute(
                sa.text(
                    """
                SELECT *
                FROM onboarding.employee_tasks
                WHERE tenant_id = :tenant_id
                  AND bundle_id = :bundle_id
                ORDER BY order_index ASC, id ASC
                """
                ),
                {"tenant_id": tenant_id, "bundle_id": UUID(str(bundle["id"]))},
            )
            .mappings()
            .all()
        )
        return dict(bundle), [dict(r) for r in tasks]

    def submit_form_task(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        task_id: UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Submit a FORM task payload (participant-only)."""

        actor = get_actor_employee_or_409(db, ctx=ctx)
        tenant_id = actor.tenant_id

        row = (
            db.execute(
                sa.text(
                    """
                SELECT t.*, b.employee_id
                FROM onboarding.employee_tasks t
                JOIN onboarding.employee_bundles b ON b.id = t.bundle_id AND b.tenant_id = t.tenant_id
                WHERE t.tenant_id = :tenant_id
                  AND t.id = :task_id
                  AND b.employee_id = :employee_id
                """
                ),
                {
                    "tenant_id": tenant_id,
                    "task_id": task_id,
                    "employee_id": actor.employee_id,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(
                code="onboarding.task.not_found",
                message="Task not found",
                status_code=404,
            )

        if str(row["task_type"]) != "FORM":
            raise AppError(
                code="onboarding.task.type_mismatch",
                message="Task is not a FORM task",
                status_code=409,
            )

        if str(row["status"]) != "PENDING":
            raise AppError(
                code="onboarding.task.not_editable",
                message="Task is not editable",
                status_code=409,
            )

        before = {"status": str(row["status"])}

        db.execute(
            sa.text(
                """
                UPDATE onboarding.employee_tasks
                SET status = 'SUBMITTED',
                    submission_payload = CAST(:payload AS jsonb),
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": task_id, "payload": json_canonical(payload)},
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="onboarding.task.submit_form",
            entity_type="onboarding.employee_task",
            entity_id=task_id,
            before=before,
            after={"status": "SUBMITTED"},
        )

        # Notify the assignee (manager/role) if resolved.
        assigned_to = row.get("assigned_to_user_id")
        if assigned_to is not None:
            assignee_id = UUID(str(assigned_to))
            enqueue_notification(
                db,
                tenant_id=tenant_id,
                recipient_user_id=assignee_id,
                template_code="onboarding.task.submitted",
                dedupe_key=f"onboarding.task.submitted:{task_id}:{assignee_id}",
                payload={
                    "title": "Onboarding form submitted",
                    "body": f"Task {row['task_code']} was submitted.",
                    "entity_type": "onboarding.employee_task",
                    "entity_id": str(task_id),
                    "action_url": "/ess/me/onboarding",
                    "correlation_id": ctx.correlation_id,
                },
            )

        db.commit()

        updated = (
            db.execute(
                sa.text(
                    "SELECT * FROM onboarding.employee_tasks WHERE tenant_id = :tenant_id AND id = :id"
                ),
                {"tenant_id": tenant_id, "id": task_id},
            )
            .mappings()
            .first()
        )
        assert updated is not None
        return dict(updated)

    def ack_task(
        self, db: Session, *, ctx: AuthContext, task_id: UUID
    ) -> dict[str, Any]:
        """
        ACK tasks are a minimal placeholder in v1.

        This endpoint exists to support "acknowledge policies" style onboarding
        items without introducing a full form engine.
        """

        actor = get_actor_employee_or_409(db, ctx=ctx)
        tenant_id = actor.tenant_id

        row = (
            db.execute(
                sa.text(
                    """
                SELECT t.*
                FROM onboarding.employee_tasks t
                JOIN onboarding.employee_bundles b ON b.id = t.bundle_id AND b.tenant_id = t.tenant_id
                WHERE t.tenant_id = :tenant_id
                  AND t.id = :task_id
                  AND b.employee_id = :employee_id
                """
                ),
                {
                    "tenant_id": tenant_id,
                    "task_id": task_id,
                    "employee_id": actor.employee_id,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(
                code="onboarding.task.not_found",
                message="Task not found",
                status_code=404,
            )

        if str(row["task_type"]) != "ACK":
            raise AppError(
                code="onboarding.task.type_mismatch",
                message="Task is not an ACK task",
                status_code=409,
            )

        if str(row["status"]) != "PENDING":
            raise AppError(
                code="onboarding.task.not_editable",
                message="Task is not editable",
                status_code=409,
            )

        now = utcnow()
        db.execute(
            sa.text(
                """
                UPDATE onboarding.employee_tasks
                SET status = 'APPROVED',
                    submission_payload = CAST(:payload AS jsonb),
                    decided_at = :decided_at,
                    decided_by_user_id = :decided_by_user_id,
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {
                "tenant_id": tenant_id,
                "id": task_id,
                "payload": json_canonical({"ack": True}),
                "decided_at": now,
                "decided_by_user_id": ctx.user_id,
            },
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="onboarding.task.ack",
            entity_type="onboarding.employee_task",
            entity_id=task_id,
            before={"status": "PENDING"},
            after={"status": "APPROVED"},
        )
        db.commit()

        updated = (
            db.execute(
                sa.text(
                    "SELECT * FROM onboarding.employee_tasks WHERE tenant_id = :tenant_id AND id = :id"
                ),
                {"tenant_id": tenant_id, "id": task_id},
            )
            .mappings()
            .first()
        )
        assert updated is not None
        return dict(updated)

    def upload_document_task(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        task_id: UUID,
        upload_file,
    ) -> dict[str, Any]:
        """
        Upload a DOCUMENT task file into DMS and link it to the onboarding task.

        Key behaviors:
        - Uses DMS LOCAL storage for bytes.
        - Creates/updates an employee document based on required_document_type_code.
        - If template requires verification, creates a DOCUMENT_VERIFICATION workflow request.
        - Keeps operations tenant-scoped and participant-safe.
        """

        actor = get_actor_employee_or_409(db, ctx=ctx)
        tenant_id = actor.tenant_id

        # Load onboarding task + template metadata needed for DMS decisions.
        row = (
            db.execute(
                sa.text(
                    """
                SELECT
                  t.*,
                  b.employee_id,
                  b.plan_template_id,
                  tt.required_document_type_code,
                  tt.requires_document_verification
                FROM onboarding.employee_tasks t
                JOIN onboarding.employee_bundles b ON b.id = t.bundle_id AND b.tenant_id = t.tenant_id
                JOIN onboarding.plan_template_tasks tt
                  ON tt.plan_template_id = b.plan_template_id
                 AND tt.tenant_id = b.tenant_id
                 AND tt.code = t.task_code
                WHERE t.tenant_id = :tenant_id
                  AND t.id = :task_id
                  AND b.employee_id = :employee_id
                """
                ),
                {
                    "tenant_id": tenant_id,
                    "task_id": task_id,
                    "employee_id": actor.employee_id,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(
                code="onboarding.task.not_found",
                message="Task not found",
                status_code=404,
            )

        if str(row["task_type"]) != "DOCUMENT":
            raise AppError(
                code="onboarding.task.type_mismatch",
                message="Task is not a DOCUMENT task",
                status_code=409,
            )

        if str(row["status"]) != "PENDING":
            raise AppError(
                code="onboarding.task.not_editable",
                message="Task is not editable",
                status_code=409,
            )

        doc_type_code = row.get("required_document_type_code")
        if not doc_type_code:
            raise AppError(
                code="validation_error",
                message="Task has no required_document_type_code",
                status_code=500,
            )

        # Step 1: upload bytes to DMS (commits internally).
        file_row = self._files.upload_file(db, ctx=ctx, upload_file=upload_file)
        file_id = UUID(str(file_row["id"]))

        # Step 2: create or update a mutable DMS document for (employee, doc_type_code).
        document_id = self._upsert_employee_document(
            db,
            ctx=ctx,
            owner_employee_id=actor.employee_id,
            document_type_code=str(doc_type_code),
            file_id=file_id,
        )

        # Step 3: optional verification workflow.
        requires_verification = bool(row.get("requires_document_verification"))
        verification_workflow_request_id: UUID | None = None
        task_status: str
        decided_at: datetime | None = None
        decided_by_user_id: UUID | None = None

        if requires_verification:
            verification_workflow_request_id = self._docs.create_verification_request(
                db, ctx=ctx, document_id=document_id
            )
            self._attach_file_to_workflow_request(
                db,
                tenant_id=tenant_id,
                workflow_request_id=verification_workflow_request_id,
                file_id=file_id,
                actor_user_id=ctx.user_id,
            )
            task_status = "SUBMITTED"
        else:
            # v1 simplification: uploading a doc completes the task immediately.
            task_status = "APPROVED"
            decided_at = utcnow()
            decided_by_user_id = ctx.user_id

        # Step 4: update onboarding task row.
        db.execute(
            sa.text(
                """
                UPDATE onboarding.employee_tasks
                SET status = :status,
                    related_document_id = :related_document_id,
                    verification_workflow_request_id = :verification_workflow_request_id,
                    decided_at = :decided_at,
                    decided_by_user_id = :decided_by_user_id,
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {
                "status": task_status,
                "related_document_id": document_id,
                "verification_workflow_request_id": verification_workflow_request_id,
                "decided_at": decided_at,
                "decided_by_user_id": decided_by_user_id,
                "tenant_id": tenant_id,
                "id": task_id,
            },
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="onboarding.task.upload_document",
            entity_type="onboarding.employee_task",
            entity_id=task_id,
            before={"status": "PENDING"},
            after={
                "status": task_status,
                "document_id": str(document_id),
                "verification_workflow_request_id": (
                    str(verification_workflow_request_id)
                    if verification_workflow_request_id is not None
                    else None
                ),
            },
        )

        # Notify employee users (idempotent).
        for uid in list_employee_user_ids(db, employee_id=actor.employee_id):
            enqueue_notification(
                db,
                tenant_id=tenant_id,
                recipient_user_id=uid,
                template_code="onboarding.document.uploaded",
                dedupe_key=f"onboarding.document.uploaded:{task_id}:{uid}",
                payload={
                    "title": "Document uploaded",
                    "body": f"Document uploaded for task {row['task_code']}.",
                    "entity_type": "onboarding.employee_task",
                    "entity_id": str(task_id),
                    "action_url": "/ess/me/onboarding",
                    "correlation_id": ctx.correlation_id,
                },
            )

        db.commit()

        updated = (
            db.execute(
                sa.text(
                    "SELECT * FROM onboarding.employee_tasks WHERE tenant_id = :tenant_id AND id = :id"
                ),
                {"tenant_id": tenant_id, "id": task_id},
            )
            .mappings()
            .first()
        )
        assert updated is not None
        return dict(updated)

    def submit_packet(
        self, db: Session, *, ctx: AuthContext, bundle_id: UUID
    ) -> dict[str, Any]:
        """
        Aggregate submitted FORM tasks into a single HR_PROFILE_CHANGE request.

        Idempotency:
        - We use profile-change idempotency key "onboarding:<bundle_id>" so that
          multiple submits return the same request (unless payload differs).
        """

        actor = get_actor_employee_or_409(db, ctx=ctx)
        tenant_id = actor.tenant_id

        bundle = (
            db.execute(
                sa.text(
                    """
                SELECT *
                FROM onboarding.employee_bundles
                WHERE tenant_id = :tenant_id
                  AND id = :bundle_id
                  AND employee_id = :employee_id
                  AND status = 'ACTIVE'
                """
                ),
                {
                    "tenant_id": tenant_id,
                    "bundle_id": bundle_id,
                    "employee_id": actor.employee_id,
                },
            )
            .mappings()
            .first()
        )
        if bundle is None:
            raise AppError(
                code="onboarding.bundle.not_found",
                message="Bundle not found",
                status_code=404,
            )

        submitted = (
            db.execute(
                sa.text(
                    """
                SELECT
                  t.id AS task_id,
                  t.order_index,
                  t.submission_payload,
                  tt.form_profile_change_mapping
                FROM onboarding.employee_tasks t
                JOIN onboarding.plan_template_tasks tt
                  ON tt.plan_template_id = :plan_template_id
                 AND tt.tenant_id = t.tenant_id
                 AND tt.code = t.task_code
                WHERE t.tenant_id = :tenant_id
                  AND t.bundle_id = :bundle_id
                  AND t.task_type = 'FORM'
                  AND t.status = 'SUBMITTED'
                ORDER BY t.order_index ASC, t.id ASC
                """
                ),
                {
                    "tenant_id": tenant_id,
                    "bundle_id": bundle_id,
                    "plan_template_id": UUID(str(bundle["plan_template_id"])),
                },
            )
            .mappings()
            .all()
        )

        if not submitted:
            raise AppError(
                code="onboarding.packet.no_submissions",
                message="No submitted form tasks to build a profile change packet",
                status_code=409,
            )

        # Deterministic merge: tasks ordered by order_index; later tasks win.
        change_set: dict[str, Any] = {}

        for r in submitted:
            mapping = r.get("form_profile_change_mapping")
            if mapping is None:
                continue
            if not isinstance(mapping, dict):
                raise AppError(
                    code="hr.profile_change.invalid_change_set",
                    message="Invalid form_profile_change_mapping",
                    status_code=400,
                )
            submission_payload = r.get("submission_payload") or {}
            if not isinstance(submission_payload, dict):
                raise AppError(
                    code="hr.profile_change.invalid_change_set",
                    message="Invalid task submission_payload",
                    status_code=400,
                )

            for target_field, source_key in mapping.items():
                if not isinstance(target_field, str) or not isinstance(source_key, str):
                    raise AppError(
                        code="hr.profile_change.invalid_change_set",
                        message="Invalid mapping entry",
                        status_code=400,
                    )
                if source_key in submission_payload:
                    change_set[target_field] = submission_payload[source_key]

        # Reuse the profile-change validator to enforce a controlled change_set.
        normalized = normalize_change_set(change_set)

        pc = self._profile_changes.create_profile_change_request(
            db,
            ctx=ctx,
            change_set=normalized,
            idempotency_key=f"onboarding:{bundle_id}",
        )

        return {
            "profile_change_request_id": UUID(str(pc["id"])),
            "workflow_request_id": UUID(str(pc["workflow_request_id"])),
        }

    # ------------------------------------------------------------------
    # DMS helpers
    # ------------------------------------------------------------------
    def _upsert_employee_document(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        owner_employee_id: UUID,
        document_type_code: str,
        file_id: UUID,
    ) -> UUID:
        """
        Create or version an employee document for a given document_type_code.

        We version only "mutable" documents:
        - status in ('DRAFT','SUBMITTED')
        - terminal docs (VERIFIED/REJECTED/EXPIRED) create a new document
        """

        tenant_id = ctx.scope.tenant_id

        existing = db.execute(
            sa.text(
                """
                SELECT d.id, d.status
                FROM dms.documents d
                JOIN dms.document_types dt ON dt.id = d.document_type_id
                WHERE d.tenant_id = :tenant_id
                  AND d.owner_employee_id = :employee_id
                  AND dt.code = :type_code
                ORDER BY d.created_at DESC, d.id DESC
                LIMIT 1
                """
            ),
            {
                "tenant_id": tenant_id,
                "employee_id": owner_employee_id,
                "type_code": document_type_code,
            },
        ).first()

        if existing is not None and str(existing[1]) in ("DRAFT", "SUBMITTED"):
            doc_id = UUID(str(existing[0]))
            self._docs.add_document_version(
                db,
                ctx=ctx,
                document_id=doc_id,
                file_id=file_id,
                notes="Onboarding upload",
            )
            return doc_id

        doc = self._docs.create_employee_document(
            db,
            ctx=ctx,
            employee_id=owner_employee_id,
            document_type_code=document_type_code,
            file_id=file_id,
            expires_at=None,
            notes="Onboarding upload",
        )
        return UUID(str(doc["id"]))

    def _attach_file_to_workflow_request(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        workflow_request_id: UUID,
        file_id: UUID,
        actor_user_id: UUID,
    ) -> None:
        """
        Mirror the file into workflow.request_attachments for a better timeline UX.

        Idempotency:
        - request_attachments has no unique constraint in baseline, so we insert
          only when (tenant_id, request_id, file_id) is missing.
        """

        db.execute(
            sa.text(
                """
                INSERT INTO workflow.request_attachments (tenant_id, request_id, file_id, created_by, note)
                SELECT :tenant_id, :request_id, :file_id, :created_by, :note
                WHERE NOT EXISTS (
                  SELECT 1
                  FROM workflow.request_attachments
                  WHERE tenant_id = :tenant_id
                    AND request_id = :request_id
                    AND file_id = :file_id
                )
                """
            ),
            {
                "tenant_id": tenant_id,
                "request_id": workflow_request_id,
                "file_id": file_id,
                "created_by": actor_user_id,
                "note": "Onboarding document",
            },
        )
