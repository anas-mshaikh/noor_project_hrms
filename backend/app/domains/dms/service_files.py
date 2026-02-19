"""
DMS file service.

This module is responsible for:
- persisting file metadata in `dms.files`
- storing file bytes on disk (LOCAL provider in v1)
- enforcing tenant isolation and "participant-safe" access checks (404 on deny)

Why separate from document service?
- A file can exist independently of a document in v1 (e.g., workflow attachments/evidence).
- Access rules are subtle; keeping them in one place prevents regressions.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi.responses import FileResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.domains.dms.storage import LocalStorageProvider
from app.shared.types import AuthContext


class DmsFileService:
    """
    High-level file operations with strict tenant scoping.
    """

    def __init__(self) -> None:
        # v1 only supports LOCAL storage. We still keep the provider object for clarity.
        self._storage = LocalStorageProvider()

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------
    def upload_file(
        self, db: Session, *, ctx: AuthContext, upload_file
    ) -> dict[str, Any]:
        """
        Persist file metadata and store bytes on disk.

        Transaction / consistency model:
        - insert row with status=UPLOADING and commit (so the file_id is reserved)
        - write bytes to disk
        - update row to READY (or FAILED) and commit
        """

        tenant_id = ctx.scope.tenant_id
        file_id = uuid4()

        original_filename = str(getattr(upload_file, "filename", None) or "file")
        content_type = str(
            getattr(upload_file, "content_type", None) or "application/octet-stream"
        )

        object_key = self._storage.build_object_key(
            tenant_id=tenant_id,
            file_id=file_id,
            original_filename=original_filename,
        )

        # Step 1: create metadata row (UPLOADING) so we have a stable file_id for references.
        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO dms.files (
                      id, tenant_id,
                      storage_provider, bucket, object_key,
                      content_type, size_bytes, sha256,
                      original_filename,
                      status,
                      created_by_user_id
                    ) VALUES (
                      :id, :tenant_id,
                      'LOCAL', NULL, :object_key,
                      :content_type, 0, NULL,
                      :original_filename,
                      'UPLOADING',
                      :created_by_user_id
                    )
                    """
                ),
                {
                    "id": file_id,
                    "tenant_id": tenant_id,
                    "object_key": object_key,
                    "content_type": content_type,
                    "original_filename": original_filename,
                    "created_by_user_id": ctx.user_id,
                },
            )
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="dms.file.upload_failed",
                message="Failed to create file metadata",
                status_code=500,
            ) from e

        # Step 2: write bytes to disk.
        try:
            result = self._storage.save_upload(
                upload_file=upload_file, object_key=object_key
            )
        except Exception as e:
            # Best-effort mark as FAILED (row exists because we committed above).
            try:
                db.execute(
                    sa.text(
                        """
                        UPDATE dms.files
                        SET status = 'FAILED',
                            updated_at = now()
                        WHERE id = :id
                          AND tenant_id = :tenant_id
                        """
                    ),
                    {"id": file_id, "tenant_id": tenant_id},
                )
                db.commit()
            except Exception:
                db.rollback()
            raise AppError(
                code="dms.file.upload_failed",
                message="File upload failed",
                status_code=500,
            ) from e

        # Step 3: finalize metadata (READY).
        db.execute(
            sa.text(
                """
                UPDATE dms.files
                SET status = 'READY',
                    size_bytes = :size_bytes,
                    sha256 = :sha256,
                    content_type = :content_type,
                    original_filename = :original_filename,
                    updated_at = now()
                WHERE id = :id
                  AND tenant_id = :tenant_id
                """
            ),
            {
                "id": file_id,
                "tenant_id": tenant_id,
                "size_bytes": int(result.size_bytes),
                "sha256": result.sha256,
                "content_type": content_type,
                "original_filename": original_filename,
            },
        )
        db.commit()

        return self.get_file_meta(db, ctx=ctx, file_id=file_id)

    # ------------------------------------------------------------------
    # Read / download (access-checked)
    # ------------------------------------------------------------------
    def get_file_meta(
        self, db: Session, *, ctx: AuthContext, file_id: UUID
    ) -> dict[str, Any]:
        """
        Return file metadata if the actor is allowed to read it.

        Security:
        - 404 on deny to avoid leaking file existence across employees/requests.
        """

        row = self._require_accessible_file_row(db, ctx=ctx, file_id=file_id)
        return dict(row)

    def download_file_response(
        self, db: Session, *, ctx: AuthContext, file_id: UUID
    ) -> FileResponse:
        """
        Return a FastAPI FileResponse for the given file_id (access-checked).
        """

        row = self._require_accessible_file_row(db, ctx=ctx, file_id=file_id)

        if str(row["status"]) != "READY":
            raise AppError(
                code="dms.file.not_ready",
                message="File is not ready for download",
                status_code=409,
            )

        object_key = str(row["object_key"])
        content_type = str(row["content_type"])
        filename = str(row["original_filename"])

        path = self._storage.resolve_abs_path(object_key=object_key)
        if not path.exists() or not path.is_file():
            # Disk is the source of truth for bytes; hide details from callers.
            raise AppError(
                code="dms.file.not_found", message="File not found", status_code=404
            )

        return FileResponse(path=str(path), filename=filename, media_type=content_type)

    # ------------------------------------------------------------------
    # Access checks
    # ------------------------------------------------------------------
    def _require_accessible_file_row(
        self, db: Session, *, ctx: AuthContext, file_id: UUID
    ) -> sa.RowMapping:
        tenant_id = ctx.scope.tenant_id

        row = (
            db.execute(
                sa.text(
                    """
                SELECT
                  id,
                  tenant_id,
                  storage_provider,
                  bucket,
                  object_key,
                  content_type,
                  size_bytes,
                  sha256,
                  original_filename,
                  status,
                  created_by_user_id,
                  created_at,
                  updated_at
                FROM dms.files
                WHERE id = :id
                  AND tenant_id = :tenant_id
                """
                ),
                {"id": file_id, "tenant_id": tenant_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(
                code="dms.file.not_found", message="File not found", status_code=404
            )

        # Creator access: allow the uploader to read/download the file even if
        # it hasn't been linked to a document/workflow yet.
        #
        # Why this exists:
        # - The upload endpoint returns file metadata immediately after upload.
        # - Onboarding/ESS flows upload a file and then link it to a document or
        #   workflow request; the link may happen after the file row exists.
        #
        # This does not create cross-tenant leaks because:
        # - the row is already filtered by tenant_id
        # - we only allow access for the same created_by_user_id
        created_by_user_id = row.get("created_by_user_id")
        if (
            created_by_user_id is not None
            and UUID(str(created_by_user_id)) == ctx.user_id
        ):
            return row

        # HR/admin-style permissions allow tenant-wide reads. We purposely do NOT
        # treat `dms:file:read` alone as privileged, because EMPLOYEE has it and
        # must be restricted to "reachable" files only.
        if self._has_privileged_file_access(ctx):
            return row

        actor_employee_id = self._get_actor_employee_id_optional(
            db, tenant_id=tenant_id, user_id=ctx.user_id
        )

        if actor_employee_id is not None and self._is_reachable_via_owned_document(
            db,
            tenant_id=tenant_id,
            file_id=file_id,
            actor_employee_id=actor_employee_id,
        ):
            return row

        if self._is_reachable_via_workflow_participant(
            db,
            tenant_id=tenant_id,
            file_id=file_id,
            actor_user_id=ctx.user_id,
        ):
            return row

        raise AppError(
            code="dms.file.not_found", message="File not found", status_code=404
        )

    def _has_privileged_file_access(self, ctx: AuthContext) -> bool:
        """
        Decide if the actor can read any file within the active tenant.

        We use higher-level DMS permissions as the "HR/admin" marker.
        """

        perms = set(ctx.permissions or ())
        return bool(
            perms.intersection(
                {
                    "dms:document:write",
                    "dms:document:verify",
                    "dms:expiry:write",
                    # Document type write implies DMS admin/config access.
                    "dms:document-type:write",
                }
            )
        )

    def _get_actor_employee_id_optional(
        self, db: Session, *, tenant_id: UUID, user_id: UUID
    ) -> UUID | None:
        """
        Resolve the employee_id linked to the current user (if any).

        NOTE: DMS file reads can be performed by non-employee actors (HR users,
        system users). For those, we simply return None and rely on privileged
        permissions or workflow participation.
        """

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
            {"user_id": user_id, "tenant_id": tenant_id},
        ).first()
        if row is None:
            return None
        return UUID(str(row[0]))

    def _is_reachable_via_owned_document(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        file_id: UUID,
        actor_employee_id: UUID,
    ) -> bool:
        """
        Allow file reads if the file is referenced by a document version owned
        by the actor's employee profile.
        """

        row = db.execute(
            sa.text(
                """
                SELECT 1
                FROM dms.document_versions dv
                JOIN dms.documents d ON d.id = dv.document_id
                WHERE dv.tenant_id = :tenant_id
                  AND dv.file_id = :file_id
                  AND d.tenant_id = :tenant_id
                  AND d.owner_employee_id = :employee_id
                LIMIT 1
                """
            ),
            {
                "tenant_id": tenant_id,
                "file_id": file_id,
                "employee_id": actor_employee_id,
            },
        ).first()
        return row is not None

    def _is_reachable_via_workflow_participant(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        file_id: UUID,
        actor_user_id: UUID,
    ) -> bool:
        """
        Allow file reads if the file is attached to a workflow request and the
        actor is a participant of that request.
        """

        # We embed participant checks directly in SQL to avoid N+1 roundtrips.
        row = db.execute(
            sa.text(
                """
                SELECT 1
                FROM workflow.request_attachments a
                JOIN workflow.requests r ON r.id = a.request_id
                WHERE a.tenant_id = :tenant_id
                  AND a.file_id = :file_id
                  AND r.tenant_id = :tenant_id
                  AND (
                    r.created_by_user_id = :user_id
                    OR EXISTS (
                      SELECT 1
                      FROM workflow.request_step_assignees rsa
                      JOIN workflow.request_steps s ON s.id = rsa.step_id
                      WHERE rsa.tenant_id = :tenant_id
                        AND rsa.user_id = :user_id
                        AND s.request_id = r.id
                    )
                    OR EXISTS (
                      SELECT 1
                      FROM hr_core.employee_user_links l
                      WHERE l.user_id = :user_id
                        AND l.employee_id = r.subject_employee_id
                    )
                  )
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id, "file_id": file_id, "user_id": actor_user_id},
        ).first()
        return row is not None
