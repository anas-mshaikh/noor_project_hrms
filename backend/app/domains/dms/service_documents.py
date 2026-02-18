"""
DMS document services (document types, employee documents, versioning, verification).

This module owns the "business record" layer:
- document types (tenant-scoped catalog)
- documents (employee-owned records with lifecycle)
- versions (immutable history; current_version_id points at the active version)
- workflow verification integration (DOCUMENT_VERIFICATION)

Access control (v1):
- HR roles can create/list documents for employees within their allowed scope
- ESS users can list/get only documents they own (participant-safe 404 on deny)
"""

from __future__ import annotations


from datetime import date, datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.workflow.service import WorkflowService
from app.shared.types import AuthContext


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DmsDocumentService:
    def __init__(self) -> None:
        self._workflow = WorkflowService()

    # ------------------------------------------------------------------
    # Document types (catalog)
    # ------------------------------------------------------------------
    def list_document_types(
        self, db: Session, *, ctx: AuthContext
    ) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id
        rows = (
            db.execute(
                sa.text(
                    """
                SELECT
                  id,
                  tenant_id,
                  code,
                  name,
                  requires_expiry,
                  is_active,
                  created_at,
                  updated_at
                FROM dms.document_types
                WHERE tenant_id = :tenant_id
                ORDER BY code ASC
                """
                ),
                {"tenant_id": tenant_id},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def create_document_type(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        code: str,
        name: str,
        requires_expiry: bool,
        is_active: bool,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        doc_type_id = uuid4()

        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO dms.document_types (
                      id, tenant_id, code, name, requires_expiry, is_active
                    ) VALUES (
                      :id, :tenant_id, :code, :name, :requires_expiry, :is_active
                    )
                    """
                ),
                {
                    "id": doc_type_id,
                    "tenant_id": tenant_id,
                    "code": code,
                    "name": name,
                    "requires_expiry": bool(requires_expiry),
                    "is_active": bool(is_active),
                },
            )

            audit_svc.record(
                db,
                ctx=ctx,
                action="dms.document_type.create",
                entity_type="dms.document_type",
                entity_id=doc_type_id,
                before=None,
                after={
                    "code": code,
                    "name": name,
                    "requires_expiry": requires_expiry,
                    "is_active": is_active,
                },
            )

            db.commit()
        except IntegrityError as e:
            db.rollback()
            # Unique (tenant_id, code) violation is the common case.
            raise AppError(
                code="validation_error",
                message="Document type code already exists",
                status_code=409,
            ) from e

        return self._get_document_type_by_id(
            db, tenant_id=tenant_id, doc_type_id=doc_type_id
        )

    def patch_document_type(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        doc_type_id: UUID,
        name: str | None,
        requires_expiry: bool | None,
        is_active: bool | None,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        before = self._get_document_type_by_id(
            db, tenant_id=tenant_id, doc_type_id=doc_type_id
        )
        if before is None:
            raise AppError(
                code="dms.document_type.not_found",
                message="Document type not found",
                status_code=404,
            )

        updates: dict[str, Any] = {}
        if name is not None:
            updates["name"] = name
        if requires_expiry is not None:
            updates["requires_expiry"] = bool(requires_expiry)
        if is_active is not None:
            updates["is_active"] = bool(is_active)

        if not updates:
            return before

        sets = ", ".join(f"{k} = :{k}" for k in updates.keys())
        updates["id"] = doc_type_id
        updates["tenant_id"] = tenant_id

        db.execute(
            sa.text(
                f"""
                UPDATE dms.document_types
                SET {sets},
                    updated_at = now()
                WHERE id = :id
                  AND tenant_id = :tenant_id
                """
            ),
            updates,
        )

        after = self._get_document_type_by_id(
            db, tenant_id=tenant_id, doc_type_id=doc_type_id
        )
        audit_svc.record(
            db,
            ctx=ctx,
            action="dms.document_type.update",
            entity_type="dms.document_type",
            entity_id=doc_type_id,
            before=before,
            after=after,
        )
        db.commit()
        return after

    def _get_document_type_by_id(
        self, db: Session, *, tenant_id: UUID, doc_type_id: UUID
    ) -> dict[str, Any] | None:
        row = (
            db.execute(
                sa.text(
                    """
                SELECT
                  id,
                  tenant_id,
                  code,
                  name,
                  requires_expiry,
                  is_active,
                  created_at,
                  updated_at
                FROM dms.document_types
                WHERE id = :id
                  AND tenant_id = :tenant_id
                """
                ),
                {"id": doc_type_id, "tenant_id": tenant_id},
            )
            .mappings()
            .first()
        )
        return dict(row) if row is not None else None

    # ------------------------------------------------------------------
    # Documents (employee-owned)
    # ------------------------------------------------------------------
    def create_employee_document(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        employee_id: UUID,
        document_type_code: str,
        file_id: UUID,
        expires_at: date | None,
        notes: str | None,
    ) -> dict[str, Any]:
        """
        Create a SUBMITTED document for an employee with version_no=1.
        """

        tenant_id = ctx.scope.tenant_id

        # Scope hardening: employee must be in tenant and within the user's allowed companies.
        emp = db.execute(
            sa.text(
                "SELECT id, company_id FROM hr_core.employees WHERE id = :id AND tenant_id = :tenant_id"
            ),
            {"id": employee_id, "tenant_id": tenant_id},
        ).first()
        if emp is None:
            raise AppError(
                code="hr.employee.not_found",
                message="Employee not found",
                status_code=404,
            )
        emp_company_id = UUID(str(emp[1]))
        if ctx.scope.allowed_company_ids and emp_company_id not in set(
            ctx.scope.allowed_company_ids
        ):
            # Avoid company existence leaks: return 404.
            raise AppError(
                code="hr.employee.not_found",
                message="Employee not found",
                status_code=404,
            )

        # Document type (must be active).
        dt = (
            db.execute(
                sa.text(
                    """
                SELECT id, code, name, requires_expiry, is_active
                FROM dms.document_types
                WHERE tenant_id = :tenant_id
                  AND code = :code
                """
                ),
                {"tenant_id": tenant_id, "code": document_type_code},
            )
            .mappings()
            .first()
        )
        if dt is None or not bool(dt.get("is_active")):
            raise AppError(
                code="dms.document_type.not_found",
                message="Document type not found",
                status_code=404,
            )

        # File must exist and be READY (and within tenant).
        f = db.execute(
            sa.text(
                """
                SELECT status
                FROM dms.files
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": file_id},
        ).first()
        if f is None:
            raise AppError(
                code="dms.file.not_found", message="File not found", status_code=404
            )
        if str(f[0]) != "READY":
            raise AppError(
                code="dms.file.not_ready", message="File is not ready", status_code=409
            )

        document_id = uuid4()
        version_id = uuid4()

        now = _utcnow()

        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO dms.documents (
                      id,
                      tenant_id,
                      document_type_id,
                      title,
                      status,
                      issued_at,
                      expires_at,
                      metadata,
                      owner_employee_id,
                      current_version_id,
                      verified_at,
                      verified_by_user_id,
                      rejected_reason,
                      created_by_user_id,
                      verification_workflow_request_id,
                      created_at,
                      updated_at
                    ) VALUES (
                      :id,
                      :tenant_id,
                      :document_type_id,
                      :title,
                      'SUBMITTED',
                      NULL,
                      :expires_at,
                      '{}'::jsonb,
                      :owner_employee_id,
                      NULL,
                      NULL,
                      NULL,
                      NULL,
                      :created_by_user_id,
                      NULL,
                      :created_at,
                      :updated_at
                    )
                    """
                ),
                {
                    "id": document_id,
                    "tenant_id": tenant_id,
                    "document_type_id": dt["id"],
                    "title": str(dt["name"]),
                    "expires_at": expires_at,
                    "owner_employee_id": employee_id,
                    "created_by_user_id": ctx.user_id,
                    "created_at": now,
                    "updated_at": now,
                },
            )

            db.execute(
                sa.text(
                    """
                    INSERT INTO dms.document_versions (
                      id, tenant_id, document_id, file_id, version, notes, created_by_user_id, created_at
                    ) VALUES (
                      :id, :tenant_id, :document_id, :file_id, 1, :notes, :created_by_user_id, :created_at
                    )
                    """
                ),
                {
                    "id": version_id,
                    "tenant_id": tenant_id,
                    "document_id": document_id,
                    "file_id": file_id,
                    "notes": notes,
                    "created_by_user_id": ctx.user_id,
                    "created_at": now,
                },
            )

            db.execute(
                sa.text(
                    """
                    UPDATE dms.documents
                    SET current_version_id = :version_id,
                        updated_at = now()
                    WHERE id = :document_id
                      AND tenant_id = :tenant_id
                    """
                ),
                {
                    "version_id": version_id,
                    "document_id": document_id,
                    "tenant_id": tenant_id,
                },
            )

            db.execute(
                sa.text(
                    """
                    INSERT INTO dms.document_links (
                      id, tenant_id, document_id, entity_type, entity_id, created_by
                    ) VALUES (
                      :id, :tenant_id, :document_id, 'hr.employee', :employee_id, :created_by
                    )
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "document_id": document_id,
                    "employee_id": employee_id,
                    "created_by": ctx.user_id,
                },
            )

            audit_svc.record(
                db,
                ctx=ctx,
                action="dms.document.create",
                entity_type="dms.document",
                entity_id=document_id,
                before=None,
                after={
                    "document_type_code": str(dt["code"]),
                    "owner_employee_id": str(employee_id),
                    "file_id": str(file_id),
                    "expires_at": str(expires_at) if expires_at is not None else None,
                },
            )

            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="dms.document.version.conflict",
                message="Document create conflict",
                status_code=409,
            ) from e

        return self.get_document_hr(db, ctx=ctx, document_id=document_id)

    def add_document_version(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        document_id: UUID,
        file_id: UUID,
        notes: str | None,
    ) -> dict[str, Any]:
        """
        Add a new immutable version and update current_version_id.

        Concurrency:
        - lock the document row FOR UPDATE to serialize version increments
        """

        tenant_id = ctx.scope.tenant_id

        doc = self._get_document_row(
            db, tenant_id=tenant_id, document_id=document_id, for_update=True
        )
        if doc is None:
            raise AppError(
                code="dms.document.not_found",
                message="Document not found",
                status_code=404,
            )

        # File must exist and be READY.
        f = db.execute(
            sa.text(
                "SELECT status FROM dms.files WHERE tenant_id = :tenant_id AND id = :id"
            ),
            {"tenant_id": tenant_id, "id": file_id},
        ).first()
        if f is None:
            raise AppError(
                code="dms.file.not_found", message="File not found", status_code=404
            )
        if str(f[0]) != "READY":
            raise AppError(
                code="dms.file.not_ready", message="File is not ready", status_code=409
            )

        max_v = db.execute(
            sa.text(
                """
                SELECT COALESCE(MAX(version), 0)
                FROM dms.document_versions
                WHERE tenant_id = :tenant_id
                  AND document_id = :document_id
                """
            ),
            {"tenant_id": tenant_id, "document_id": document_id},
        ).scalar()
        next_v = int(max_v or 0) + 1

        version_id = uuid4()
        now = _utcnow()

        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO dms.document_versions (
                      id, tenant_id, document_id, file_id, version, notes, created_by_user_id, created_at
                    ) VALUES (
                      :id, :tenant_id, :document_id, :file_id, :version, :notes, :created_by_user_id, :created_at
                    )
                    """
                ),
                {
                    "id": version_id,
                    "tenant_id": tenant_id,
                    "document_id": document_id,
                    "file_id": file_id,
                    "version": next_v,
                    "notes": notes,
                    "created_by_user_id": ctx.user_id,
                    "created_at": now,
                },
            )
            db.execute(
                sa.text(
                    """
                    UPDATE dms.documents
                    SET current_version_id = :version_id,
                        updated_at = now()
                    WHERE id = :document_id
                      AND tenant_id = :tenant_id
                    """
                ),
                {
                    "version_id": version_id,
                    "document_id": document_id,
                    "tenant_id": tenant_id,
                },
            )

            audit_svc.record(
                db,
                ctx=ctx,
                action="dms.document.new_version",
                entity_type="dms.document",
                entity_id=document_id,
                before={
                    "current_version_id": str(doc.get("current_version_id"))
                    if doc.get("current_version_id")
                    else None
                },
                after={
                    "current_version_id": str(version_id),
                    "version": next_v,
                    "file_id": str(file_id),
                },
            )
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="dms.document.version.conflict",
                message="Version conflict",
                status_code=409,
            ) from e

        return self.get_document_hr(db, ctx=ctx, document_id=document_id)

    # ------------------------------------------------------------------
    # Read paths
    # ------------------------------------------------------------------
    def list_employee_documents_hr(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        employee_id: UUID,
        status: str | None,
        type_code: str | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        HR list endpoint for one employee.
        """

        tenant_id = ctx.scope.tenant_id

        # Validate employee in tenant + allowed companies (no leaks).
        emp = db.execute(
            sa.text(
                "SELECT company_id FROM hr_core.employees WHERE id = :id AND tenant_id = :tenant_id"
            ),
            {"id": employee_id, "tenant_id": tenant_id},
        ).first()
        if emp is None:
            raise AppError(
                code="hr.employee.not_found",
                message="Employee not found",
                status_code=404,
            )
        emp_company_id = UUID(str(emp[0]))
        if ctx.scope.allowed_company_ids and emp_company_id not in set(
            ctx.scope.allowed_company_ids
        ):
            raise AppError(
                code="hr.employee.not_found",
                message="Employee not found",
                status_code=404,
            )

        where = ["d.tenant_id = :tenant_id", "d.owner_employee_id = :employee_id"]
        params: dict[str, Any] = {
            "tenant_id": tenant_id,
            "employee_id": employee_id,
            "limit": int(limit),
        }

        if status:
            where.append("d.status = :status")
            params["status"] = status
        if type_code:
            where.append("dt.code = :type_code")
            params["type_code"] = type_code
        if cursor is not None:
            ts, cid = cursor
            where.append("(d.created_at, d.id) < (:cursor_ts, :cursor_id)")
            params["cursor_ts"] = ts
            params["cursor_id"] = cid

        sql = f"""
            SELECT
              d.id,
              d.tenant_id,
              d.document_type_id,
              dt.code AS document_type_code,
              dt.name AS document_type_name,
              d.owner_employee_id,
              d.status,
              d.expires_at,
              d.current_version_id,
              d.verified_at,
              d.verified_by_user_id,
              d.rejected_reason,
              d.created_by_user_id,
              d.verification_workflow_request_id,
              d.created_at,
              d.updated_at,
              cv.file_id AS current_file_id,
              cv.version AS current_version_no,
              cv.notes AS current_version_notes,
              cv.created_by_user_id AS current_version_created_by_user_id,
              cv.created_at AS current_version_created_at
            FROM dms.documents d
            JOIN dms.document_types dt ON dt.id = d.document_type_id
            LEFT JOIN dms.document_versions cv ON cv.id = d.current_version_id
            WHERE {" AND ".join(where)}
            ORDER BY d.created_at DESC, d.id DESC
            LIMIT :limit
        """

        rows = db.execute(sa.text(sql), params).mappings().all()
        items = [self._row_to_document_out(r) for r in rows]
        next_cursor = None
        if len(items) == limit and rows:
            last = rows[-1]
            next_cursor = f"{last['created_at'].isoformat()}|{last['id']}"
        return items, next_cursor

    def list_my_documents_ess(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        status: str | None,
        type_code: str | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        """
        ESS list endpoint: actor can only see documents they own.
        """

        employee_id = self._require_actor_employee_id(db, ctx=ctx)
        return self.list_employee_documents_hr(
            db,
            ctx=ctx,
            employee_id=employee_id,
            status=status,
            type_code=type_code,
            limit=limit,
            cursor=cursor,
        )

    def get_document_hr(
        self, db: Session, *, ctx: AuthContext, document_id: UUID
    ) -> dict[str, Any]:
        """
        HR/internal get path used after mutations.
        """

        tenant_id = ctx.scope.tenant_id
        row = (
            db.execute(
                sa.text(
                    """
                SELECT
                  d.id,
                  d.tenant_id,
                  d.document_type_id,
                  dt.code AS document_type_code,
                  dt.name AS document_type_name,
                  d.owner_employee_id,
                  d.status,
                  d.expires_at,
                  d.current_version_id,
                  d.verified_at,
                  d.verified_by_user_id,
                  d.rejected_reason,
                  d.created_by_user_id,
                  d.verification_workflow_request_id,
                  d.created_at,
                  d.updated_at,
                  cv.file_id AS current_file_id,
                  cv.version AS current_version_no,
                  cv.notes AS current_version_notes,
                  cv.created_by_user_id AS current_version_created_by_user_id,
                  cv.created_at AS current_version_created_at
                FROM dms.documents d
                JOIN dms.document_types dt ON dt.id = d.document_type_id
                LEFT JOIN dms.document_versions cv ON cv.id = d.current_version_id
                WHERE d.tenant_id = :tenant_id
                  AND d.id = :id
                """
                ),
                {"tenant_id": tenant_id, "id": document_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(
                code="dms.document.not_found",
                message="Document not found",
                status_code=404,
            )
        return self._row_to_document_out(row)

    def get_my_document_ess(
        self, db: Session, *, ctx: AuthContext, document_id: UUID
    ) -> dict[str, Any]:
        """
        ESS get endpoint with participant-only semantics (404 on deny).
        """

        tenant_id = ctx.scope.tenant_id
        employee_id = self._require_actor_employee_id(db, ctx=ctx)

        row = (
            db.execute(
                sa.text(
                    """
                SELECT
                  d.id,
                  d.tenant_id,
                  d.document_type_id,
                  dt.code AS document_type_code,
                  dt.name AS document_type_name,
                  d.owner_employee_id,
                  d.status,
                  d.expires_at,
                  d.current_version_id,
                  d.verified_at,
                  d.verified_by_user_id,
                  d.rejected_reason,
                  d.created_by_user_id,
                  d.verification_workflow_request_id,
                  d.created_at,
                  d.updated_at,
                  cv.file_id AS current_file_id,
                  cv.version AS current_version_no,
                  cv.notes AS current_version_notes,
                  cv.created_by_user_id AS current_version_created_by_user_id,
                  cv.created_at AS current_version_created_at
                FROM dms.documents d
                JOIN dms.document_types dt ON dt.id = d.document_type_id
                LEFT JOIN dms.document_versions cv ON cv.id = d.current_version_id
                WHERE d.tenant_id = :tenant_id
                  AND d.id = :id
                  AND d.owner_employee_id = :employee_id
                """
                ),
                {"tenant_id": tenant_id, "id": document_id, "employee_id": employee_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(
                code="dms.document.not_found",
                message="Document not found",
                status_code=404,
            )
        return self._row_to_document_out(row)

    # ------------------------------------------------------------------
    # Verification (workflow)
    # ------------------------------------------------------------------
    def create_verification_request(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        document_id: UUID,
    ) -> UUID:
        """
        Create (or reuse) a workflow request for verifying a document.

        We store the workflow_request_id on the document for convenience.
        """

        tenant_id = ctx.scope.tenant_id

        doc = self._get_document_row(
            db, tenant_id=tenant_id, document_id=document_id, for_update=True
        )
        if doc is None:
            raise AppError(
                code="dms.document.not_found",
                message="Document not found",
                status_code=404,
            )

        status = str(doc["status"])
        if status in ("VERIFIED", "REJECTED", "EXPIRED"):
            raise AppError(
                code="dms.document.verify.already_terminal",
                message="Document is already in a terminal state",
                status_code=409,
            )

        existing_req = doc.get("verification_workflow_request_id")
        if existing_req is not None:
            # Idempotent behavior: if we already created one, reuse it.
            return UUID(str(existing_req))

        owner_employee_id = doc.get("owner_employee_id")
        if owner_employee_id is None:
            raise AppError(
                code="dms.document.not_found",
                message="Document not found",
                status_code=404,
            )

        # Need document type metadata for workflow payload (compact, non-sensitive).
        dt = db.execute(
            sa.text(
                """
                SELECT dt.code, dt.name
                FROM dms.document_types dt
                WHERE dt.id = :id
                  AND dt.tenant_id = :tenant_id
                """
            ),
            {"id": doc["document_type_id"], "tenant_id": tenant_id},
        ).first()
        if dt is None:
            raise AppError(
                code="dms.document_type.not_found",
                message="Document type not found",
                status_code=404,
            )
        dt_code = str(dt[0])

        payload = {
            "document_id": str(document_id),
            "document_type_code": dt_code,
            "expires_at": str(doc.get("expires_at"))
            if doc.get("expires_at") is not None
            else None,
        }

        wf = self._workflow.create_request(
            db,
            ctx=ctx,
            request_type_code="DOCUMENT_VERIFICATION",
            payload=payload,
            subject_employee_id=UUID(str(owner_employee_id)),
            entity_type="dms.document",
            entity_id=document_id,
            company_id_hint=ctx.scope.company_id,
            branch_id_hint=ctx.scope.branch_id,
            # Do NOT use workflow idempotency keys here: if a verify workflow is
            # cancelled and the document is resubmitted, we want a fresh request.
            idempotency_key=None,
            initial_comment=None,
            commit=False,
        )

        wf_request_id = UUID(str(wf["id"]))

        db.execute(
            sa.text(
                """
                UPDATE dms.documents
                SET verification_workflow_request_id = :workflow_request_id,
                    updated_at = now()
                WHERE id = :id
                  AND tenant_id = :tenant_id
                """
            ),
            {
                "workflow_request_id": wf_request_id,
                "id": document_id,
                "tenant_id": tenant_id,
            },
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="dms.document.verify_request.create",
            entity_type="dms.document",
            entity_id=document_id,
            before={"verification_workflow_request_id": None},
            after={"verification_workflow_request_id": str(wf_request_id)},
        )

        db.commit()
        return wf_request_id

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _require_actor_employee_id(self, db: Session, *, ctx: AuthContext) -> UUID:
        tenant_id = ctx.scope.tenant_id
        row = db.execute(
            sa.text(
                """
                SELECT e.id
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
        return UUID(str(row[0]))

    def _get_document_row(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        document_id: UUID,
        for_update: bool,
    ) -> dict[str, Any] | None:
        """
        Fetch a document row (minimal columns) with optional FOR UPDATE.
        """

        lock = "FOR UPDATE" if for_update else ""
        row = (
            db.execute(
                sa.text(
                    f"""
                SELECT
                  id,
                  tenant_id,
                  document_type_id,
                  owner_employee_id,
                  status,
                  expires_at,
                  current_version_id,
                  verification_workflow_request_id
                FROM dms.documents
                WHERE tenant_id = :tenant_id
                  AND id = :id
                {lock}
                """
                ),
                {"tenant_id": tenant_id, "id": document_id},
            )
            .mappings()
            .first()
        )
        return dict(row) if row is not None else None

    def _row_to_document_out(self, row: dict[str, Any]) -> dict[str, Any]:
        """
        Convert a joined SELECT row into the DocumentOut DTO shape.
        """

        current_version = None
        if row.get("current_version_id") is not None:
            current_version = {
                "id": row["current_version_id"],
                "tenant_id": row["tenant_id"],
                "document_id": row["id"],
                "file_id": row.get("current_file_id"),
                "version": int(row.get("current_version_no") or 0),
                "notes": row.get("current_version_notes"),
                "created_by_user_id": row.get("current_version_created_by_user_id"),
                "created_at": row.get("current_version_created_at"),
            }

        return {
            "id": row["id"],
            "tenant_id": row["tenant_id"],
            "document_type_id": row["document_type_id"],
            "document_type_code": str(row.get("document_type_code") or ""),
            "document_type_name": str(row.get("document_type_name") or ""),
            "owner_employee_id": row.get("owner_employee_id"),
            "status": str(row.get("status") or ""),
            "expires_at": row.get("expires_at"),
            "current_version_id": row.get("current_version_id"),
            "current_version": current_version,
            "verified_at": row.get("verified_at"),
            "verified_by_user_id": row.get("verified_by_user_id"),
            "rejected_reason": row.get("rejected_reason"),
            "created_by_user_id": row.get("created_by_user_id"),
            "verification_workflow_request_id": row.get(
                "verification_workflow_request_id"
            ),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
