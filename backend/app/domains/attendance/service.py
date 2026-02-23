from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.config import settings
from app.core.errors import AppError
from app.domains.workflow.service import WorkflowService
from app.shared.types import AuthContext


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AttendanceCorrectionService:
    def __init__(self) -> None:
        self._workflow = WorkflowService()

    # ------------------------------------------------------------------
    # Actor resolution
    # ------------------------------------------------------------------
    def get_actor_employee_or_409(self, db: Session, *, ctx: AuthContext) -> tuple[UUID, UUID, UUID]:
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
            raise AppError(code="ess.not_linked", message="User is not linked to an employee", status_code=409)
        employee_id, company_id = row
        return UUID(str(employee_id)), tenant_id, UUID(str(company_id))

    def get_current_employment(self, db: Session, *, tenant_id: UUID, employee_id: UUID) -> dict[str, Any]:
        row = db.execute(
            sa.text(
                """
                SELECT company_id, branch_id
                FROM hr_core.v_employee_current_employment
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id},
        ).mappings().first()
        if row is None:
            raise AppError(code="validation_error", message="Employee has no current employment", status_code=400)
        return dict(row)

    # ------------------------------------------------------------------
    # Validations
    # ------------------------------------------------------------------
    def validate_day_window(self, *, day: date, now: datetime) -> None:
        max_back = int(settings.attendance_correction_max_days_back)
        oldest = now.date() - timedelta(days=max_back)
        if day < oldest:
            raise AppError(code="attendance.correction.too_old", message="Correction day is too old", status_code=400)

        if (not bool(settings.attendance_correction_allow_future_days)) and (day > now.date()):
            raise AppError(
                code="attendance.correction.future_not_allowed",
                message="Correction for future day is not allowed",
                status_code=400,
            )

    def validate_reason(self, *, reason: str | None) -> None:
        if not bool(settings.attendance_correction_require_reason):
            return
        if reason is None or reason.strip() == "":
            raise AppError(
                code="attendance.correction.reason_required",
                message="Reason is required",
                status_code=400,
            )

    def validate_no_leave_conflict(self, db: Session, *, tenant_id: UUID, employee_id: UUID, day: date) -> None:
        row = db.execute(
            sa.text(
                """
                SELECT 1
                FROM attendance.day_overrides
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND day = :day
                  AND status = 'ON_LEAVE'
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id, "day": day},
        ).first()
        if row is not None:
            raise AppError(
                code="attendance.correction.conflict.leave",
                message="Day is on leave and cannot be corrected",
                status_code=409,
            )

    def validate_pending_unique_day(self, db: Session, *, tenant_id: UUID, employee_id: UUID, day: date) -> None:
        row = db.execute(
            sa.text(
                """
                SELECT 1
                FROM attendance.attendance_corrections
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND day = :day
                  AND status = 'PENDING'
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id, "day": day},
        ).first()
        if row is not None:
            raise AppError(
                code="attendance.correction.pending_exists",
                message="A pending correction already exists for this day",
                status_code=409,
            )

    # ------------------------------------------------------------------
    # ESS day view
    # ------------------------------------------------------------------
    def get_my_days(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        start: date,
        end: date,
    ) -> list[dict[str, Any]]:
        employee_id, tenant_id, _company_id = self.get_actor_employee_or_409(db, ctx=ctx)

        if end < start:
            raise AppError(code="validation_error", message="to must be >= from", status_code=400)

        # Base attendance is derived from attendance.attendance_daily:
        # - if a row exists for the day -> base_status=PRESENT
        # - otherwise -> base_status=ABSENT
        #
        # We intentionally do NOT filter by branch_id here. Employees can move
        # branches over time, and historical days should still be readable.
        base_rows = (
            db.execute(
            sa.text(
                """
                SELECT
                  business_date,
                  punch_in,
                  punch_out,
                  total_minutes,
                  source_breakdown,
                  has_open_session
                FROM attendance.attendance_daily
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND business_date >= :start
                  AND business_date <= :end
                ORDER BY business_date ASC, created_at ASC, id ASC
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id, "start": start, "end": end},
            )
            .mappings()
            .all()
        )

        base_by_day: dict[date, dict[str, Any]] = {r["business_date"]: dict(r) for r in base_rows}

        overrides = (
            db.execute(
            sa.text(
                """
                SELECT
                  day,
                  override_kind,
                  status,
                  source_type,
                  source_id,
                  payload,
                  created_at
                FROM attendance.day_overrides
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                  AND day >= :start
                  AND day <= :end
                ORDER BY created_at DESC, id DESC
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id, "start": start, "end": end},
            )
            .mappings()
            .all()
        )

        leave_by_day: dict[date, dict[str, Any]] = {}
        corr_by_day: dict[date, dict[str, Any]] = {}
        for o in overrides:
            d = o["day"]
            if str(o["status"]) == "ON_LEAVE":
                # Leave wins regardless of correction overrides.
                if d not in leave_by_day:
                    leave_by_day[d] = dict(o)
                continue

            # Newest correction wins (order is created_at DESC).
            if d not in corr_by_day:
                corr_by_day[d] = dict(o)

        items: list[dict[str, Any]] = []
        cur = start
        while cur <= end:
            base_row = base_by_day.get(cur)
            base_status = "PRESENT" if base_row is not None else "ABSENT"
            base_minutes = int(base_row.get("total_minutes") or 0) if base_row is not None else 0

            # Convenience fields for UI/debug. These are purely derived and can be NULL.
            first_in = base_row.get("punch_in") if base_row is not None else None
            last_out = base_row.get("punch_out") if base_row is not None else None
            has_open_session = bool(base_row.get("has_open_session") or False) if base_row is not None else False

            src_breakdown = base_row.get("source_breakdown") if base_row is not None else None
            sources: list[str] = []
            if isinstance(src_breakdown, dict):
                # Stable ordering for deterministic API responses.
                sources = sorted(str(k) for k in src_breakdown.keys())

            if cur in leave_by_day:
                o = leave_by_day[cur]
                items.append(
                    {
                        "day": cur,
                        "base_status": base_status,
                        "effective_status": "ON_LEAVE",
                        "base_minutes": base_minutes,
                        "effective_minutes": 0,
                        "first_in": first_in,
                        "last_out": last_out,
                        "has_open_session": has_open_session,
                        "sources": sources,
                        "override": {
                            "kind": "LEAVE",
                            "status": "ON_LEAVE",
                            "source_type": str(o["source_type"]),
                            "source_id": UUID(str(o["source_id"])),
                        },
                    }
                )
                cur += timedelta(days=1)
                continue

            if cur in corr_by_day:
                o = corr_by_day[cur]
                kind = str(o.get("override_kind") or "CORRECTION")
                status = str(o["status"])

                # Minutes precedence:
                # 1) ON_LEAVE -> 0 (handled above)
                # 2) CORRECTION payload.override_minutes if present
                # 3) ABSENT_OVERRIDE implies 0 minutes
                # 4) otherwise base_minutes
                effective_minutes = base_minutes
                payload = o.get("payload") or {}
                if isinstance(payload, dict) and payload.get("override_minutes") is not None:
                    try:
                        effective_minutes = int(payload.get("override_minutes"))
                    except Exception:
                        effective_minutes = base_minutes
                elif status == "ABSENT_OVERRIDE":
                    effective_minutes = 0

                items.append(
                    {
                        "day": cur,
                        "base_status": base_status,
                        "effective_status": status,
                        "base_minutes": base_minutes,
                        "effective_minutes": int(effective_minutes),
                        "first_in": first_in,
                        "last_out": last_out,
                        "has_open_session": has_open_session,
                        "sources": sources,
                        "override": {
                            "kind": "CORRECTION" if kind != "LEAVE" else "LEAVE",
                            "status": status,
                            "source_type": str(o["source_type"]),
                            "source_id": UUID(str(o["source_id"])),
                        },
                    }
                )
                cur += timedelta(days=1)
                continue

            items.append(
                {
                    "day": cur,
                    "base_status": base_status,
                    "effective_status": base_status,
                    "base_minutes": base_minutes,
                    "effective_minutes": base_minutes,
                    "first_in": first_in,
                    "last_out": last_out,
                    "has_open_session": has_open_session,
                    "sources": sources,
                    "override": None,
                }
            )
            cur += timedelta(days=1)

        return items

    # ------------------------------------------------------------------
    # ESS corrections
    # ------------------------------------------------------------------
    def list_my_corrections(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        status: str | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        employee_id, tenant_id, _company_id = self.get_actor_employee_or_409(db, ctx=ctx)
        cursor_ts = cursor[0] if cursor else None
        cursor_id = cursor[1] if cursor else None

        where_parts = ["c.tenant_id = :tenant_id", "c.employee_id = :employee_id"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "employee_id": employee_id, "limit": int(limit)}
        if status:
            where_parts.append("c.status = :status")
            params["status"] = status.strip().upper()
        if cursor_ts is not None and cursor_id is not None:
            where_parts.append("(c.created_at, c.id) < (:cursor_ts, :cursor_id)")
            params["cursor_ts"] = cursor_ts
            params["cursor_id"] = cursor_id

        rows = db.execute(
            sa.text(
                f"""
                SELECT c.*
                FROM attendance.attendance_corrections c
                WHERE {' AND '.join(where_parts)}
                ORDER BY c.created_at DESC, c.id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        items = [dict(r) for r in rows]

        next_cursor = None
        if len(items) == int(limit) and items:
            last = items[-1]
            next_cursor = f"{last['created_at'].isoformat()}|{last['id']}"
        return items, next_cursor

    def create_my_correction(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        day: date,
        correction_type: str,
        requested_override_status: str,
        reason: str | None,
        evidence_file_ids: list[UUID],
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        employee_id, tenant_id, _company_id = self.get_actor_employee_or_409(db, ctx=ctx)

        file_ids = [UUID(str(x)) for x in (evidence_file_ids or [])]

        # Idempotency (correction-level): must be checked BEFORE pending-per-day
        # validation so callers can safely retry and get the original record.
        if idempotency_key:
            existing = db.execute(
                sa.text(
                    """
                    SELECT c.*
                    FROM attendance.attendance_corrections c
                    WHERE c.tenant_id = :tenant_id
                      AND c.employee_id = :employee_id
                      AND c.idempotency_key = :key
                    ORDER BY c.created_at DESC, c.id DESC
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id, "employee_id": employee_id, "key": idempotency_key},
            ).mappings().first()
            if existing is not None:
                same = True
                same = same and existing["day"] == day
                same = same and str(existing["correction_type"]) == str(correction_type)
                same = same and str(existing["requested_override_status"]) == str(requested_override_status)
                same = same and (existing.get("reason") or None) == (reason or None)
                # evidence_file_ids is stored as uuid[]; compare as sets.
                existing_ids = {UUID(str(x)) for x in (existing.get("evidence_file_ids") or [])}
                same = same and existing_ids == set(file_ids)
                if not same:
                    raise AppError(
                        code="attendance.correction.idempotency.conflict",
                        message="Idempotency key already used with different payload",
                        status_code=409,
                    )
                return dict(existing)

        now = _utcnow()
        self.validate_day_window(day=day, now=now)
        self.validate_reason(reason=reason)
        self.validate_no_leave_conflict(db, tenant_id=tenant_id, employee_id=employee_id, day=day)
        self.validate_pending_unique_day(db, tenant_id=tenant_id, employee_id=employee_id, day=day)

        employment = self.get_current_employment(db, tenant_id=tenant_id, employee_id=employee_id)
        employment_company_id = UUID(str(employment["company_id"]))
        employment_branch_id = UUID(str(employment["branch_id"]))

        if file_ids:
            found = db.execute(
                sa.text(
                    """
                    SELECT id
                    FROM dms.files
                    WHERE tenant_id = :tenant_id
                      AND id = ANY(CAST(:ids AS uuid[]))
                    """
                ),
                {"tenant_id": tenant_id, "ids": file_ids},
            ).all()
            if len(found) != len(file_ids):
                raise AppError(code="validation_error", message="Invalid evidence_file_ids", status_code=400)

        correction_id = uuid4()

        wf_payload = {
            "day": day.isoformat(),
            "correction_type": str(correction_type),
            "requested_override_status": str(requested_override_status),
        }
        if reason:
            wf_payload["reason"] = reason

        wf = self._workflow.create_request(
            db,
            ctx=ctx,
            request_type_code="ATTENDANCE_CORRECTION",
            payload=wf_payload,
            subject_employee_id=employee_id,
            entity_type="attendance.attendance_correction",
            entity_id=correction_id,
            company_id_hint=employment_company_id,
            branch_id_hint=employment_branch_id,
            idempotency_key=(f"attendance_correction:{idempotency_key}" if idempotency_key else None),
            initial_comment=None,
            commit=False,
        )
        workflow_request_id = UUID(str(wf["id"]))

        try:
            row = db.execute(
                sa.text(
                    """
                    INSERT INTO attendance.attendance_corrections (
                      id, tenant_id, employee_id, branch_id, day,
                      correction_type, requested_override_status,
                      reason, evidence_file_ids,
                      status, workflow_request_id, idempotency_key
                    ) VALUES (
                      :id, :tenant_id, :employee_id, :branch_id, :day,
                      :correction_type, :requested_override_status,
                      :reason, CAST(:evidence_file_ids AS uuid[]),
                      'PENDING', :workflow_request_id, :idempotency_key
                    )
                    RETURNING *
                    """
                ),
                {
                    "id": correction_id,
                    "tenant_id": tenant_id,
                    "employee_id": employee_id,
                    "branch_id": employment_branch_id,
                    "day": day,
                    "correction_type": str(correction_type),
                    "requested_override_status": str(requested_override_status),
                    "reason": reason,
                    "evidence_file_ids": file_ids,
                    "workflow_request_id": workflow_request_id,
                    "idempotency_key": idempotency_key,
                },
            ).mappings().first()
        except IntegrityError as e:
            db.rollback()
            if idempotency_key:
                existing = db.execute(
                    sa.text(
                        """
                        SELECT c.*
                        FROM attendance.attendance_corrections c
                        WHERE c.tenant_id = :tenant_id
                          AND c.employee_id = :employee_id
                          AND c.idempotency_key = :key
                        ORDER BY c.created_at DESC, c.id DESC
                        LIMIT 1
                        """
                    ),
                    {"tenant_id": tenant_id, "employee_id": employee_id, "key": idempotency_key},
                ).mappings().first()
                if existing is not None:
                    same = True
                    same = same and existing["day"] == day
                    same = same and str(existing["correction_type"]) == str(correction_type)
                    same = same and str(existing["requested_override_status"]) == str(requested_override_status)
                    same = same and (existing.get("reason") or None) == (reason or None)
                    existing_ids = {UUID(str(x)) for x in (existing.get("evidence_file_ids") or [])}
                    same = same and existing_ids == set(file_ids)
                    if not same:
                        raise AppError(
                            code="attendance.correction.idempotency.conflict",
                            message="Idempotency key already used with different payload",
                            status_code=409,
                        ) from e
                    return dict(existing)
            raise AppError(code="attendance.correction.pending_exists", message="A pending correction already exists for this day", status_code=409) from e

        assert row is not None

        for fid in file_ids:
            db.execute(
                sa.text(
                    """
                    INSERT INTO workflow.request_attachments (tenant_id, request_id, file_id, created_by, note)
                    VALUES (:tenant_id, :request_id, :file_id, :created_by, :note)
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "request_id": workflow_request_id,
                    "file_id": fid,
                    "created_by": ctx.user_id,
                    "note": "Attendance correction evidence",
                },
            )

        audit_svc.record(
            db,
            ctx=ctx,
            action="attendance.correction.create",
            entity_type="attendance.attendance_correction",
            entity_id=correction_id,
            before=None,
            after={
                "day": day.isoformat(),
                "correction_type": str(correction_type),
                "requested_override_status": str(requested_override_status),
                "workflow_request_id": str(workflow_request_id),
            },
        )
        db.commit()
        return dict(row)

    def cancel_my_correction(self, db: Session, *, ctx: AuthContext, correction_id: UUID) -> dict[str, Any]:
        employee_id, tenant_id, _company_id = self.get_actor_employee_or_409(db, ctx=ctx)

        corr = db.execute(
            sa.text(
                """
                SELECT id, employee_id, status, workflow_request_id
                FROM attendance.attendance_corrections
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": correction_id},
        ).mappings().first()
        if corr is None:
            raise AppError(code="attendance.correction.not_found", message="Correction not found", status_code=404)
        if UUID(str(corr["employee_id"])) != employee_id:
            raise AppError(code="attendance.correction.not_found", message="Correction not found", status_code=404)
        if str(corr["status"]) != "PENDING":
            raise AppError(code="attendance.correction.not_pending", message="Correction is not pending", status_code=409)
        if corr.get("workflow_request_id") is None:
            raise AppError(code="attendance.correction.not_found", message="Correction has no workflow link", status_code=404)

        workflow_request_id = UUID(str(corr["workflow_request_id"]))
        self._workflow.cancel_request(db, ctx=ctx, request_id=workflow_request_id)

        updated = db.execute(
            sa.text(
                """
                SELECT *
                FROM attendance.attendance_corrections
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": correction_id},
        ).mappings().first()
        assert updated is not None
        return dict(updated)

    # ------------------------------------------------------------------
    # Admin list
    # ------------------------------------------------------------------
    def admin_list_corrections(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        status: str | None,
        branch_id: UUID | None,
        start: date | None,
        end: date | None,
        limit: int,
        cursor: tuple[datetime, UUID] | None,
    ) -> tuple[list[dict[str, Any]], str | None]:
        tenant_id = ctx.scope.tenant_id
        cursor_ts = cursor[0] if cursor else None
        cursor_id = cursor[1] if cursor else None

        where_parts = ["c.tenant_id = :tenant_id"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "limit": int(limit)}
        if status:
            where_parts.append("c.status = :status")
            params["status"] = status.strip().upper()
        if branch_id is not None:
            where_parts.append("c.branch_id = :branch_id")
            params["branch_id"] = branch_id
        if start is not None:
            where_parts.append("c.day >= :start")
            params["start"] = start
        if end is not None:
            where_parts.append("c.day <= :end")
            params["end"] = end
        if cursor_ts is not None and cursor_id is not None:
            where_parts.append("(c.created_at, c.id) < (:cursor_ts, :cursor_id)")
            params["cursor_ts"] = cursor_ts
            params["cursor_id"] = cursor_id

        rows = db.execute(
            sa.text(
                f"""
                SELECT c.*
                FROM attendance.attendance_corrections c
                WHERE {' AND '.join(where_parts)}
                ORDER BY c.created_at DESC, c.id DESC
                LIMIT :limit
                """
            ),
            params,
        ).mappings().all()
        items = [dict(r) for r in rows]

        next_cursor = None
        if len(items) == int(limit) and items:
            last = items[-1]
            next_cursor = f"{last['created_at'].isoformat()}|{last['id']}"
        return items, next_cursor

    # ------------------------------------------------------------------
    # Workflow hooks (terminal side-effects)
    # ------------------------------------------------------------------
    def _load_correction_for_update(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        correction_id: UUID,
    ) -> dict[str, Any] | None:
        row = db.execute(
            sa.text(
                """
                SELECT *
                FROM attendance.attendance_corrections
                WHERE tenant_id = :tenant_id
                  AND id = :id
                FOR UPDATE
                """
            ),
            {"tenant_id": tenant_id, "id": correction_id},
        ).mappings().first()
        return dict(row) if row is not None else None

    def on_workflow_approved(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        tenant_id = ctx.scope.tenant_id
        entity_id = workflow_request.get("entity_id")
        if entity_id is None:
            return
        correction_id = UUID(str(entity_id))

        corr = self._load_correction_for_update(db, tenant_id=tenant_id, correction_id=correction_id)
        if corr is None:
            return
        if str(corr["status"]) == "APPROVED":
            return
        if str(corr["status"]) != "PENDING":
            return

        employee_id = UUID(str(corr["employee_id"]))
        branch_id = UUID(str(corr["branch_id"]))
        day = corr["day"]
        requested_override_status = str(corr["requested_override_status"])
        correction_type = str(corr["correction_type"])
        reason = corr.get("reason")

        # Race-safe recheck: corrections cannot override leave days in v1.
        self.validate_no_leave_conflict(db, tenant_id=tenant_id, employee_id=employee_id, day=day)

        db.execute(
            sa.text(
                """
                INSERT INTO attendance.day_overrides (
                  tenant_id, employee_id, branch_id, day,
                  status, source_type, source_id,
                  override_kind, notes, payload
                ) VALUES (
                  :tenant_id, :employee_id, :branch_id, :day,
                  :status, 'ATTENDANCE_CORRECTION', :source_id,
                  'CORRECTION', :notes, CAST(:payload AS jsonb)
                )
                ON CONFLICT (tenant_id, employee_id, day, source_type, source_id) DO NOTHING
                """
            ),
            {
                "tenant_id": tenant_id,
                "employee_id": employee_id,
                "branch_id": branch_id,
                "day": day,
                "status": requested_override_status,
                "source_id": correction_id,
                "notes": reason,
                "payload": json.dumps({"correction_type": correction_type}, default=str),
            },
        )

        db.execute(
            sa.text(
                """
                UPDATE attendance.attendance_corrections
                SET status = 'APPROVED',
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": correction_id},
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="attendance.correction.approved",
            entity_type="attendance.attendance_correction",
            entity_id=correction_id,
            before={"status": "PENDING"},
            after={"status": "APPROVED", "workflow_request_id": str(workflow_request.get("id"))},
        )

    def on_workflow_rejected(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        tenant_id = ctx.scope.tenant_id
        entity_id = workflow_request.get("entity_id")
        if entity_id is None:
            return
        correction_id = UUID(str(entity_id))

        corr = self._load_correction_for_update(db, tenant_id=tenant_id, correction_id=correction_id)
        if corr is None:
            return
        if str(corr["status"]) == "REJECTED":
            return
        if str(corr["status"]) != "PENDING":
            return

        db.execute(
            sa.text(
                """
                UPDATE attendance.attendance_corrections
                SET status = 'REJECTED',
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": correction_id},
        )
        audit_svc.record(
            db,
            ctx=ctx,
            action="attendance.correction.rejected",
            entity_type="attendance.attendance_correction",
            entity_id=correction_id,
            before={"status": "PENDING"},
            after={"status": "REJECTED", "workflow_request_id": str(workflow_request.get("id"))},
        )

    def on_workflow_cancelled(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        tenant_id = ctx.scope.tenant_id
        entity_id = workflow_request.get("entity_id")
        if entity_id is None:
            return
        correction_id = UUID(str(entity_id))

        corr = self._load_correction_for_update(db, tenant_id=tenant_id, correction_id=correction_id)
        if corr is None:
            return
        if str(corr["status"]) == "CANCELED":
            return
        if str(corr["status"]) != "PENDING":
            return

        db.execute(
            sa.text(
                """
                UPDATE attendance.attendance_corrections
                SET status = 'CANCELED',
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": correction_id},
        )
        audit_svc.record(
            db,
            ctx=ctx,
            action="attendance.correction.cancel",
            entity_type="attendance.attendance_correction",
            entity_id=correction_id,
            before={"status": "PENDING"},
            after={"status": "CANCELED", "workflow_request_id": str(workflow_request.get("id"))},
        )
