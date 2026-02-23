"""
Payslip publish and ESS read services (Milestone 9).

v1 publishes payslips as JSON files stored in DMS (LOCAL storage).
We do not render PDFs in v1.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.dms.service_files import DmsFileService
from app.domains.dms.storage import LocalStorageProvider
from app.domains.payroll.utils import json_canonical, utcnow
from app.shared.types import AuthContext


@dataclass(frozen=True)
class ActorEmployee:
    employee_id: UUID
    tenant_id: UUID


def _write_bytes_atomic(*, dest_abs, data: bytes) -> tuple[int, str]:
    """
    Write bytes atomically to a destination path.

    We follow the same safety model as DMS uploads:
    - write to "<dest>.part"
    - rename atomically (POSIX)

    Returns:
      (size_bytes, sha256_hex)
    """

    dest_abs.parent.mkdir(parents=True, exist_ok=True)

    tmp_abs = dest_abs.with_suffix(dest_abs.suffix + ".part")
    h = hashlib.sha256()
    size = 0

    try:
        with tmp_abs.open("wb") as out:
            out.write(data)
            h.update(data)
            size = len(data)
        tmp_abs.replace(dest_abs)
        return int(size), h.hexdigest()
    finally:
        if tmp_abs.exists():
            try:
                tmp_abs.unlink()
            except Exception:
                pass


def _list_employee_user_ids(db: Session, *, tenant_id: UUID, employee_id: UUID) -> list[UUID]:
    rows = db.execute(
        sa.text(
            """
            SELECT user_id
            FROM hr_core.employee_user_links
            WHERE employee_id = :employee_id
            ORDER BY created_at ASC, user_id ASC
            """
        ),
        {"employee_id": employee_id},
    ).all()
    return [UUID(str(r[0])) for r in rows]


def _enqueue_outbox(
    db: Session,
    *,
    tenant_id: UUID,
    recipient_user_id: UUID,
    template_code: str,
    dedupe_key: str,
    payload: dict[str, object],
) -> None:
    db.execute(
        sa.text(
            """
            INSERT INTO workflow.notification_outbox (
              tenant_id, channel, recipient_user_id, template_code, payload, dedupe_key
            ) VALUES (
              :tenant_id, 'IN_APP', :recipient_user_id, :template_code, CAST(:payload AS jsonb), :dedupe_key
            )
            ON CONFLICT (tenant_id, channel, dedupe_key) WHERE dedupe_key IS NOT NULL DO NOTHING
            """
        ),
        {
            "tenant_id": tenant_id,
            "recipient_user_id": recipient_user_id,
            "template_code": template_code,
            "payload": json_canonical(payload),
            "dedupe_key": dedupe_key,
        },
    )


class PayslipService:
    """Publish payruns into payslips and serve ESS payslip reads/downloads."""

    def __init__(self) -> None:
        self._storage = LocalStorageProvider()
        self._files = DmsFileService()

    # ------------------------------------------------------------------
    # Actor resolution
    # ------------------------------------------------------------------
    def get_actor_employee_or_409(self, db: Session, *, ctx: AuthContext) -> ActorEmployee:
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
            raise AppError(code="ess.not_linked", message="User is not linked to an employee", status_code=409)
        return ActorEmployee(employee_id=UUID(str(row[0])), tenant_id=tenant_id)

    # ------------------------------------------------------------------
    # Publish
    # ------------------------------------------------------------------
    def publish_payrun(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        payrun_id: UUID,
    ) -> dict[str, Any]:
        """
        Publish an approved payrun by generating payslips and storing them in DMS.

        Concurrency:
        - Locks the payrun row FOR UPDATE.

        Transaction model:
        - We write file bytes to disk first (atomic rename), then insert DB rows.
        - If the DB transaction rolls back, bytes may be orphaned (acceptable);
          the DB is the source of truth for discoverability.
        """

        tenant_id = ctx.scope.tenant_id

        payrun = (
            db.execute(
                sa.text(
                    """
                    SELECT pr.id, pr.status, pr.branch_id, pr.period_id, p.period_key
                    FROM payroll.payruns pr
                    JOIN payroll.periods p ON p.id = pr.period_id AND p.tenant_id = pr.tenant_id
                    WHERE pr.tenant_id = :tenant_id
                      AND pr.id = :id
                    FOR UPDATE
                    """
                ),
                {"tenant_id": tenant_id, "id": payrun_id},
            )
            .mappings()
            .first()
        )
        if payrun is None:
            raise AppError(code="payroll.payrun.not_found", message="Payrun not found", status_code=404)

        # Scope hardening: branch-scoped tokens must match.
        if ctx.scope.branch_id is not None and UUID(str(payrun["branch_id"])) != ctx.scope.branch_id:
            raise AppError(code="payroll.payrun.not_found", message="Payrun not found", status_code=404)

        status = str(payrun["status"])
        if status == "PUBLISHED":
            raise AppError(code="payroll.payrun.already_published", message="Payrun already published", status_code=409)
        if status != "APPROVED":
            raise AppError(code="payroll.payrun.not_approved", message="Payrun is not approved", status_code=409)

        period_key = str(payrun["period_key"])

        # Ensure PAYSLIP document type exists for this tenant (covers future tenants).
        db.execute(
            sa.text(
                """
                INSERT INTO dms.document_types (tenant_id, code, name, requires_expiry, is_active)
                VALUES (:tenant_id, 'PAYSLIP', 'Payslip', false, true)
                ON CONFLICT (tenant_id, code) DO NOTHING
                """
            ),
            {"tenant_id": tenant_id},
        )
        dt = (
            db.execute(
                sa.text(
                    """
                    SELECT id, name
                    FROM dms.document_types
                    WHERE tenant_id = :tenant_id
                      AND code = 'PAYSLIP'
                    """
                ),
                {"tenant_id": tenant_id},
            )
            .mappings()
            .first()
        )
        assert dt is not None
        doc_type_id = UUID(str(dt["id"]))
        doc_type_name = str(dt["name"] or "Payslip")

        items = (
            db.execute(
                sa.text(
                    """
                    SELECT
                      i.id AS payrun_item_id,
                      i.employee_id,
                      i.gross_amount,
                      i.deductions_amount,
                      i.net_amount,
                      i.payable_days,
                      i.working_days_in_period,
                      i.computed_json
                    FROM payroll.payrun_items i
                    WHERE i.tenant_id = :tenant_id
                      AND i.payrun_id = :payrun_id
                      AND i.status = 'INCLUDED'
                    ORDER BY i.employee_id ASC, i.id ASC
                    """
                ),
                {"tenant_id": tenant_id, "payrun_id": payrun_id},
            )
            .mappings()
            .all()
        )

        published = 0

        for it in items:
            employee_id = UUID(str(it["employee_id"]))

            # Upsert payslip row and fetch id.
            payslip_row = (
                db.execute(
                    sa.text(
                        """
                        INSERT INTO payroll.payslips (
                          id, tenant_id, payrun_id, employee_id, status, dms_document_id
                        ) VALUES (
                          :id, :tenant_id, :payrun_id, :employee_id, 'READY', NULL
                        )
                        ON CONFLICT (tenant_id, payrun_id, employee_id)
                        DO UPDATE SET updated_at = now()
                        RETURNING *
                        """
                    ),
                    {
                        "id": uuid4(),
                        "tenant_id": tenant_id,
                        "payrun_id": payrun_id,
                        "employee_id": employee_id,
                    },
                )
                .mappings()
                .first()
            )
            assert payslip_row is not None
            payslip_id = UUID(str(payslip_row["id"]))

            # If already linked to a document (unexpected in v1), skip regeneration.
            if payslip_row.get("dms_document_id") is not None:
                continue

            # Build payslip JSON payload (v1: simple and non-PII).
            payslip_payload = {
                "payslip_id": str(payslip_id),
                "payrun_id": str(payrun_id),
                "period_key": period_key,
                "employee_id": str(employee_id),
                "totals": {
                    "gross_amount": str(it["gross_amount"]),
                    "deductions_amount": str(it["deductions_amount"]),
                    "net_amount": str(it["net_amount"]),
                },
                "attendance": {
                    "payable_days": int(it["payable_days"] or 0),
                    "working_days_in_period": int(it["working_days_in_period"] or 0),
                },
                "computed": it.get("computed_json") or {},
            }

            data = (json_canonical(payslip_payload) + "\n").encode("utf-8")
            file_id = uuid4()
            object_key = self._storage.build_object_key(
                tenant_id=tenant_id,
                file_id=file_id,
                original_filename=f"payslip_{period_key}.json",
            )
            dest_abs = self._storage.resolve_abs_path(object_key=object_key)
            size_bytes, sha256_hex = _write_bytes_atomic(dest_abs=dest_abs, data=data)

            # Insert dms.files row (READY).
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
                      'application/json', :size_bytes, :sha256,
                      :original_filename,
                      'READY',
                      :created_by_user_id
                    )
                    """
                ),
                {
                    "id": file_id,
                    "tenant_id": tenant_id,
                    "object_key": object_key,
                    "size_bytes": int(size_bytes),
                    "sha256": sha256_hex,
                    "original_filename": f"payslip_{period_key}.json",
                    "created_by_user_id": ctx.user_id,
                },
            )

            document_id = uuid4()
            version_id = uuid4()
            now = utcnow()

            # Create DMS document + version and point current_version_id.
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
                      NULL,
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
                    "document_type_id": doc_type_id,
                    "title": f"{doc_type_name} {period_key}",
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
                      :id, :tenant_id, :document_id, :file_id, 1, NULL, :created_by_user_id, :created_at
                    )
                    """
                ),
                {
                    "id": version_id,
                    "tenant_id": tenant_id,
                    "document_id": document_id,
                    "file_id": file_id,
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
                    WHERE tenant_id = :tenant_id
                      AND id = :document_id
                    """
                ),
                {"tenant_id": tenant_id, "document_id": document_id, "version_id": version_id},
            )

            db.execute(
                sa.text(
                    """
                    INSERT INTO dms.document_links (
                      id, tenant_id, document_id, entity_type, entity_id, created_by
                    ) VALUES (
                      :id, :tenant_id, :document_id, 'payroll.payslip', :entity_id, :created_by
                    )
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "id": uuid4(),
                    "tenant_id": tenant_id,
                    "document_id": document_id,
                    "entity_id": payslip_id,
                    "created_by": ctx.user_id,
                },
            )

            db.execute(
                sa.text(
                    """
                    UPDATE payroll.payslips
                    SET status = 'PUBLISHED',
                        dms_document_id = :document_id,
                        updated_at = now()
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                    """
                ),
                {"tenant_id": tenant_id, "id": payslip_id, "document_id": document_id},
            )

            # Notify linked users (no salary amounts in payload).
            for user_id in _list_employee_user_ids(db, tenant_id=tenant_id, employee_id=employee_id):
                _enqueue_outbox(
                    db,
                    tenant_id=tenant_id,
                    recipient_user_id=user_id,
                    template_code="payroll.payslip.published",
                    dedupe_key=f"payslip:published:{payrun_id}:{employee_id}:{user_id}",
                    payload={
                        "title": "Payslip published",
                        "body": f"Your payslip for {period_key} is available.",
                        "entity_type": "payroll.payslip",
                        "entity_id": str(payslip_id),
                        "payrun_id": str(payrun_id),
                        "period_key": period_key,
                    },
                )

            published += 1

        db.execute(
            sa.text(
                """
                UPDATE payroll.payruns
                SET status = 'PUBLISHED',
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": payrun_id},
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="payroll.payrun.published",
            entity_type="payroll.payrun",
            entity_id=payrun_id,
            before={"status": "APPROVED"},
            after={"status": "PUBLISHED", "published_count": int(published)},
        )

        db.commit()
        return {"payrun_id": str(payrun_id), "published_count": int(published), "status": "PUBLISHED"}

    # ------------------------------------------------------------------
    # ESS reads
    # ------------------------------------------------------------------
    def list_my_payslips(
        self, db: Session, *, ctx: AuthContext, year: int
    ) -> list[dict[str, Any]]:
        actor = self.get_actor_employee_or_409(db, ctx=ctx)
        tenant_id = actor.tenant_id
        employee_id = actor.employee_id

        prefix = f"{int(year):04d}-"
        rows = (
            db.execute(
                sa.text(
                    """
                    SELECT
                      ps.*,
                      p.period_key
                    FROM payroll.payslips ps
                    JOIN payroll.payruns pr ON pr.id = ps.payrun_id AND pr.tenant_id = ps.tenant_id
                    JOIN payroll.periods p ON p.id = pr.period_id AND p.tenant_id = pr.tenant_id
                    WHERE ps.tenant_id = :tenant_id
                      AND ps.employee_id = :employee_id
                      AND p.period_key LIKE :prefix
                    ORDER BY p.period_key DESC, ps.created_at DESC, ps.id DESC
                    """
                ),
                {"tenant_id": tenant_id, "employee_id": employee_id, "prefix": f"{prefix}%"},
            )
            .mappings()
            .all()
        )
        return [dict(r) for r in rows]

    def get_my_payslip(
        self, db: Session, *, ctx: AuthContext, payslip_id: UUID
    ) -> dict[str, Any]:
        actor = self.get_actor_employee_or_409(db, ctx=ctx)
        tenant_id = actor.tenant_id

        row = (
            db.execute(
                sa.text(
                    """
                    SELECT
                      ps.*,
                      p.period_key
                    FROM payroll.payslips ps
                    JOIN payroll.payruns pr ON pr.id = ps.payrun_id AND pr.tenant_id = ps.tenant_id
                    JOIN payroll.periods p ON p.id = pr.period_id AND p.tenant_id = pr.tenant_id
                    WHERE ps.tenant_id = :tenant_id
                      AND ps.id = :id
                      AND ps.employee_id = :employee_id
                    """
                ),
                {"tenant_id": tenant_id, "id": payslip_id, "employee_id": actor.employee_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            # Participant-safe.
            raise AppError(code="payroll.payslip.not_found", message="Payslip not found", status_code=404)
        return dict(row)

    def download_my_payslip(
        self, db: Session, *, ctx: AuthContext, payslip_id: UUID
    ) -> FileResponse:
        actor = self.get_actor_employee_or_409(db, ctx=ctx)
        tenant_id = actor.tenant_id

        row = db.execute(
            sa.text(
                """
                SELECT
                  dv.file_id
                FROM payroll.payslips ps
                JOIN dms.documents d
                  ON d.id = ps.dms_document_id
                 AND d.tenant_id = ps.tenant_id
                JOIN dms.document_versions dv
                  ON dv.id = d.current_version_id
                 AND dv.tenant_id = d.tenant_id
                WHERE ps.tenant_id = :tenant_id
                  AND ps.id = :id
                  AND ps.employee_id = :employee_id
                """
            ),
            {"tenant_id": tenant_id, "id": payslip_id, "employee_id": actor.employee_id},
        ).first()
        if row is None:
            raise AppError(code="payroll.payslip.not_found", message="Payslip not found", status_code=404)

        file_id = UUID(str(row[0]))
        return self._files.download_file_response(db, ctx=ctx, file_id=file_id)

