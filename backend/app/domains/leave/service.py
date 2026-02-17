from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.leave import repo
from app.domains.workflow.service import WorkflowService
from app.shared.types import AuthContext


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _period_year(*, year_start_month: int, d: date) -> int:
    # Leave-year boundary rule:
    # period_year(d) = d.year if d.month >= year_start_month else d.year - 1
    return d.year if d.month >= int(year_start_month) else (d.year - 1)


def _decimal_days(value: float | int | Decimal) -> Decimal:
    if isinstance(value, Decimal):
        return value
    # Avoid float surprises: 0.5 is safe but keep canonical string conversion.
    return Decimal(str(value))


@dataclass(frozen=True)
class ComputedDays:
    rows: list[dict[str, Any]]
    requested_days: Decimal


class LeaveService:
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
                SELECT company_id, branch_id, manager_employee_id
                FROM hr_core.v_employee_current_employment
                WHERE tenant_id = :tenant_id
                  AND employee_id = :employee_id
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id},
        ).mappings().first()
        if row is None:
            raise AppError(code="leave.policy.missing", message="Employee has no current employment", status_code=400)
        return dict(row)

    # ------------------------------------------------------------------
    # Policy / types
    # ------------------------------------------------------------------
    def _get_active_policy_for_employee(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        employee_id: UUID,
        employment_company_id: UUID,
        employment_branch_id: UUID,
        at_date: date,
    ) -> dict[str, Any]:
        policy_id = repo.get_active_employee_policy_id(
            db,
            tenant_id=tenant_id,
            employee_id=employee_id,
            at_date=at_date,
        )
        if policy_id is None:
            raise AppError(code="leave.policy.missing", message="No active leave policy for employee", status_code=400)

        pol = repo.get_policy_by_id(db, tenant_id=tenant_id, policy_id=policy_id)
        if pol is None:
            raise AppError(code="leave.policy.missing", message="Leave policy not found", status_code=400)

        if not bool(pol.get("is_active", True)):
            raise AppError(code="leave.policy.missing", message="Leave policy is not active", status_code=400)

        if pol.get("company_id") is not None and UUID(str(pol["company_id"])) != employment_company_id:
            raise AppError(code="leave.policy.missing", message="Leave policy does not match employee company", status_code=400)
        if pol.get("branch_id") is not None and UUID(str(pol["branch_id"])) != employment_branch_id:
            raise AppError(code="leave.policy.missing", message="Leave policy does not match employee branch", status_code=400)

        # Policy effective dating (separate from employee assignment)
        eff_from = pol.get("effective_from")
        eff_to = pol.get("effective_to")
        if eff_from is not None and at_date < eff_from:
            raise AppError(code="leave.policy.missing", message="Leave policy is not effective yet", status_code=400)
        if eff_to is not None and at_date > eff_to:
            raise AppError(code="leave.policy.missing", message="Leave policy is not effective", status_code=400)

        return pol

    # ------------------------------------------------------------------
    # Calendar computation
    # ------------------------------------------------------------------
    def compute_request_days(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        start_date: date,
        end_date: date,
        unit: str,
        half_day_part: str | None,
    ) -> ComputedDays:
        weekly = repo.list_weekly_off(db, tenant_id=tenant_id, branch_id=branch_id)
        weekdays = {int(r["weekday"]) for r in weekly}
        if len(weekly) != 7 or weekdays != set(range(7)):
            raise AppError(
                code="leave.calendar.missing",
                message="Weekly off calendar is not configured for the branch",
                status_code=400,
            )
        is_off_by_weekday = {int(r["weekday"]): bool(r["is_off"]) for r in weekly}

        # Holidays for range: branch-specific overrides global holidays.
        holiday_rows = db.execute(
            sa.text(
                """
                SELECT day, name, branch_id
                FROM leave.holidays
                WHERE tenant_id = :tenant_id
                  AND day >= :start_date
                  AND day <= :end_date
                  AND (
                    branch_id = :branch_id
                    OR (branch_id IS NULL AND company_id IS NULL)
                  )
                """
            ),
            {"tenant_id": tenant_id, "branch_id": branch_id, "start_date": start_date, "end_date": end_date},
        ).mappings().all()

        holiday_by_day: dict[date, str] = {}
        for r in holiday_rows:
            b = r.get("branch_id")
            if b is None:
                # global; set only if no branch override exists
                holiday_by_day.setdefault(r["day"], str(r["name"]))
        for r in holiday_rows:
            b = r.get("branch_id")
            if b is not None and UUID(str(b)) == branch_id:
                holiday_by_day[r["day"]] = str(r["name"])

        # Expand days.
        if unit == "HALF_DAY":
            day_fraction = Decimal("0.5")
        else:
            day_fraction = Decimal("1.0")

        cur = start_date
        rows: list[dict[str, Any]] = []
        total = Decimal("0")
        while cur <= end_date:
            wd = cur.weekday()  # 0=Mon..6
            weekend = bool(is_off_by_weekday.get(wd, False))
            hol_name = holiday_by_day.get(cur)
            is_holiday = hol_name is not None
            countable = (not weekend) and (not is_holiday)
            if countable:
                total += day_fraction
            rows.append(
                {
                    "day": cur,
                    "countable": countable,
                    "day_fraction": day_fraction,
                    "is_weekend": weekend,
                    "is_holiday": is_holiday,
                    "holiday_name": hol_name,
                }
            )
            cur = cur + timedelta(days=1)

        if total <= 0:
            raise AppError(code="leave.invalid_range", message="Selected range has no working days", status_code=400)

        return ComputedDays(rows=rows, requested_days=total)

    # ------------------------------------------------------------------
    # ESS APIs
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
        employee_id, tenant_id, _company_id = self.get_actor_employee_or_409(db, ctx=ctx)
        cursor_ts = cursor[0] if cursor else None
        cursor_id = cursor[1] if cursor else None

        where_parts = ["r.tenant_id = :tenant_id", "r.employee_id = :employee_id"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "employee_id": employee_id, "limit": int(limit)}
        if status:
            where_parts.append("r.status = :status")
            params["status"] = status.strip().upper()
        if cursor_ts is not None and cursor_id is not None:
            where_parts.append("(r.created_at, r.id) < (:cursor_ts, :cursor_id)")
            params["cursor_ts"] = cursor_ts
            params["cursor_id"] = cursor_id

        rows = db.execute(
            sa.text(
                f"""
                SELECT
                  r.*,
                  lt.code AS leave_type_code,
                  lt.name AS leave_type_name
                FROM leave.leave_requests r
                JOIN leave.leave_types lt ON lt.id = r.leave_type_id
                WHERE {' AND '.join(where_parts)}
                ORDER BY r.created_at DESC, r.id DESC
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

    def get_my_balances(self, db: Session, *, ctx: AuthContext, year: int) -> list[dict[str, Any]]:
        employee_id, tenant_id, _company_id = self.get_actor_employee_or_409(db, ctx=ctx)

        # Balance/used from ledger.
        rows = db.execute(
            sa.text(
                """
                SELECT
                  lt.id AS leave_type_id,
                  lt.code,
                  lt.name,
                  COALESCE(SUM(l.delta_days), 0) AS balance_days,
                  COALESCE(SUM(CASE WHEN l.source_type = 'LEAVE_REQUEST' AND l.delta_days < 0 THEN -l.delta_days ELSE 0 END), 0) AS used_days
                FROM leave.leave_types lt
                LEFT JOIN leave.leave_ledger l
                  ON l.tenant_id = lt.tenant_id
                 AND l.leave_type_id = lt.id
                 AND l.employee_id = :employee_id
                 AND l.period_year = :year
                WHERE lt.tenant_id = :tenant_id
                  AND lt.is_active = true
                GROUP BY lt.id, lt.code, lt.name
                ORDER BY lt.code ASC
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id, "year": int(year)},
        ).mappings().all()

        pending_rows = db.execute(
            sa.text(
                """
                SELECT
                  r.leave_type_id,
                  COALESCE(SUM(r.requested_days), 0) AS pending_days
                FROM leave.leave_requests r
                JOIN leave.leave_policies p ON p.id = r.policy_id
                WHERE r.tenant_id = :tenant_id
                  AND r.employee_id = :employee_id
                  AND r.status = 'PENDING'
                  AND (
                    CASE
                      WHEN EXTRACT(MONTH FROM r.start_date)::int >= p.year_start_month THEN EXTRACT(YEAR FROM r.start_date)::int
                      ELSE (EXTRACT(YEAR FROM r.start_date)::int - 1)
                    END
                  ) = :year
                GROUP BY r.leave_type_id
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id, "year": int(year)},
        ).mappings().all()
        pending_by_type = {UUID(str(r["leave_type_id"])): Decimal(str(r["pending_days"])) for r in pending_rows}

        items: list[dict[str, Any]] = []
        for r in rows:
            lt_id = UUID(str(r["leave_type_id"]))
            bal = Decimal(str(r["balance_days"]))
            used = Decimal(str(r["used_days"]))
            pending = pending_by_type.get(lt_id, Decimal("0"))
            items.append(
                {
                    "leave_type_code": str(r["code"]),
                    "leave_type_name": str(r["name"]),
                    "period_year": int(year),
                    "balance_days": float(bal),
                    "used_days": float(used),
                    "pending_days": float(pending),
                }
            )
        return items

    def create_my_request(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        leave_type_code: str,
        start_date: date,
        end_date: date,
        unit: str,
        half_day_part: str | None,
        reason: str | None,
        attachment_file_ids: list[UUID],
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        employee_id, tenant_id, _company_id = self.get_actor_employee_or_409(db, ctx=ctx)

        if start_date > end_date:
            raise AppError(code="leave.invalid_range", message="start_date must be <= end_date", status_code=400)

        unit_norm = unit.strip().upper()
        if unit_norm not in {"DAY", "HALF_DAY"}:
            raise AppError(code="leave.invalid_range", message="Invalid unit", status_code=400)

        if unit_norm == "HALF_DAY":
            if start_date != end_date:
                raise AppError(code="leave.half_day.invalid", message="HALF_DAY requires a single day", status_code=400)
            if not half_day_part:
                raise AppError(code="leave.half_day.invalid", message="half_day_part is required", status_code=400)

        # Current employment determines company/branch for policy + calendar.
        emp = self.get_current_employment(db, tenant_id=tenant_id, employee_id=employee_id)
        employment_company_id = UUID(str(emp["company_id"]))
        employment_branch_id = UUID(str(emp["branch_id"]))

        # Ensure active scope aligns (workflow engine uses ctx.scope for company/branch).
        if ctx.scope.company_id is None or ctx.scope.branch_id is None:
            raise AppError(code="iam.scope.invalid_company", message="Company and branch scope are required", status_code=400)
        if ctx.scope.company_id != employment_company_id or ctx.scope.branch_id != employment_branch_id:
            raise AppError(code="iam.scope.mismatch", message="Active scope does not match employee employment", status_code=400)

        lt = repo.get_leave_type_by_code(db, tenant_id=tenant_id, code=leave_type_code)
        if lt is None or not bool(lt.get("is_active", True)):
            raise AppError(code="leave.type.not_found", message="Leave type not found", status_code=404)
        leave_type_id = UUID(str(lt["id"]))

        policy = self._get_active_policy_for_employee(
            db,
            tenant_id=tenant_id,
            employee_id=employee_id,
            employment_company_id=employment_company_id,
            employment_branch_id=employment_branch_id,
            at_date=start_date,
        )
        policy_id = UUID(str(policy["id"]))
        year_start_month = int(policy["year_start_month"])

        period_year = _period_year(year_start_month=year_start_month, d=start_date)
        if _period_year(year_start_month=year_start_month, d=end_date) != period_year:
            raise AppError(code="leave.invalid_range", message="Leave cannot span multiple leave years", status_code=400)

        rule = repo.get_policy_rule(db, tenant_id=tenant_id, policy_id=policy_id, leave_type_id=leave_type_id)
        if rule is None:
            raise AppError(code="leave.policy.rule.missing", message="Leave policy has no rule for this type", status_code=400)

        allow_half_day = bool(rule.get("allow_half_day", False))
        if unit_norm == "HALF_DAY" and not allow_half_day:
            raise AppError(code="leave.half_day.invalid", message="Half-day is not allowed for this leave type", status_code=400)

        # Calendar compute (requires weekly_off config).
        computed = self.compute_request_days(
            db,
            tenant_id=tenant_id,
            branch_id=employment_branch_id,
            start_date=start_date,
            end_date=end_date,
            unit=unit_norm,
            half_day_part=half_day_part,
        )
        requested_days = computed.requested_days

        # Attachment requirement (policy override > type default).
        requires_attachment_override = rule.get("requires_attachment")
        effective_requires_attachment = (
            bool(requires_attachment_override) if requires_attachment_override is not None else bool(lt.get("requires_attachment", False))
        )
        if effective_requires_attachment and not attachment_file_ids:
            raise AppError(code="leave.attachment_required", message="Attachment is required for this leave type", status_code=400)

        # Validate attachment file ids (if provided/required).
        file_ids = list(dict.fromkeys(attachment_file_ids))  # stable dedupe
        if file_ids:
            found = db.execute(
                sa.text("SELECT id FROM dms.files WHERE tenant_id = :tenant_id AND id = ANY(:ids)"),
                {"tenant_id": tenant_id, "ids": file_ids},
            ).all()
            if len(found) != len(file_ids):
                raise AppError(code="leave.attachment_required", message="Invalid attachment_file_ids", status_code=400)

        # Idempotency (leave-level).
        if idempotency_key:
            existing = db.execute(
                sa.text(
                    """
                    SELECT
                      r.*,
                      lt.code AS leave_type_code,
                      lt.name AS leave_type_name
                    FROM leave.leave_requests r
                    JOIN leave.leave_types lt ON lt.id = r.leave_type_id
                    WHERE r.tenant_id = :tenant_id
                      AND r.employee_id = :employee_id
                      AND r.idempotency_key = :key
                    ORDER BY r.created_at DESC, r.id DESC
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id, "employee_id": employee_id, "key": idempotency_key},
            ).mappings().first()
            if existing is not None:
                same = True
                same = same and UUID(str(existing["leave_type_id"])) == leave_type_id
                same = same and existing["start_date"] == start_date
                same = same and existing["end_date"] == end_date
                same = same and str(existing["unit"]) == unit_norm
                same = same and (existing.get("half_day_part") == half_day_part)
                same = same and Decimal(str(existing["requested_days"])) == requested_days
                if not same:
                    raise AppError(
                        code="leave.idempotency.conflict",
                        message="Idempotency key already used with different payload",
                        status_code=409,
                    )
                return dict(existing)

        # Overlap check against PENDING/APPROVED requests.
        days = [r["day"] for r in computed.rows]
        overlap = db.execute(
            sa.text(
                """
                SELECT 1
                FROM leave.leave_request_days d
                JOIN leave.leave_requests r ON r.id = d.leave_request_id
                WHERE d.tenant_id = :tenant_id
                  AND d.employee_id = :employee_id
                  AND d.day = ANY(CAST(:days AS date[]))
                  AND r.status IN ('PENDING','APPROVED')
                LIMIT 1
                """
            ),
            {"tenant_id": tenant_id, "employee_id": employee_id, "days": days},
        ).first()
        if overlap is not None:
            raise AppError(code="leave.overlap", message="Leave request overlaps with an existing request", status_code=409)

        # Balance check (rechecked on approval as well).
        balance = repo.get_balance(
            db,
            tenant_id=tenant_id,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            period_year=period_year,
        )
        allow_negative = bool(lt.get("allow_negative_balance", False))
        if (requested_days > balance) and (not allow_negative):
            raise AppError(code="leave.insufficient_balance", message="Insufficient leave balance", status_code=409)

        leave_request_id = uuid4()

        # Create workflow request in the SAME transaction (no commit yet).
        wf_payload = {
            "subject": f"Leave request: {leave_type_code} {start_date.isoformat()} to {end_date.isoformat()}",
            "leave_type_code": leave_type_code,
            "start_date": start_date.isoformat(),
            "end_date": end_date.isoformat(),
            "unit": unit_norm,
            "half_day_part": half_day_part,
            "requested_days": float(requested_days),
        }
        wf = self._workflow.create_request(
            db,
            ctx=ctx,
            request_type_code="LEAVE_REQUEST",
            payload=wf_payload,
            subject_employee_id=employee_id,
            entity_type="leave.leave_request",
            entity_id=leave_request_id,
            company_id_hint=employment_company_id,
            branch_id_hint=employment_branch_id,
            idempotency_key=(f"leave:{idempotency_key}" if idempotency_key else None),
            initial_comment=None,
            commit=False,
        )
        workflow_request_id = UUID(str(wf["id"]))

        # Insert leave domain record + exploded days.
        try:
            db.execute(
                sa.text(
                    """
                    INSERT INTO leave.leave_requests (
                      id, tenant_id, employee_id, leave_type_id, policy_id,
                      start_date, end_date, unit, half_day_part, requested_days,
                      reason, status, workflow_request_id, company_id, branch_id, idempotency_key
                    ) VALUES (
                      :id, :tenant_id, :employee_id, :leave_type_id, :policy_id,
                      :start_date, :end_date, :unit, :half_day_part, :requested_days,
                      :reason, 'PENDING', :workflow_request_id, :company_id, :branch_id, :idempotency_key
                    )
                    """
                ),
                {
                    "id": leave_request_id,
                    "tenant_id": tenant_id,
                    "employee_id": employee_id,
                    "leave_type_id": leave_type_id,
                    "policy_id": policy_id,
                    "start_date": start_date,
                    "end_date": end_date,
                    "unit": unit_norm,
                    "half_day_part": half_day_part,
                    "requested_days": requested_days,
                    "reason": reason,
                    "workflow_request_id": workflow_request_id,
                    "company_id": employment_company_id,
                    "branch_id": employment_branch_id,
                    "idempotency_key": idempotency_key,
                },
            )
        except IntegrityError as e:
            db.rollback()
            raise AppError(code="leave.idempotency.conflict", message="Idempotency key already used", status_code=409) from e

        for r in computed.rows:
            db.execute(
                sa.text(
                    """
                    INSERT INTO leave.leave_request_days (
                      tenant_id, leave_request_id, employee_id,
                      day, countable, day_fraction, is_weekend, is_holiday, holiday_name
                    ) VALUES (
                      :tenant_id, :leave_request_id, :employee_id,
                      :day, :countable, :day_fraction, :is_weekend, :is_holiday, :holiday_name
                    )
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "leave_request_id": leave_request_id,
                    "employee_id": employee_id,
                    "day": r["day"],
                    "countable": bool(r["countable"]),
                    "day_fraction": r["day_fraction"],
                    "is_weekend": bool(r["is_weekend"]),
                    "is_holiday": bool(r["is_holiday"]),
                    "holiday_name": r.get("holiday_name"),
                },
            )

        # Mirror attachments into workflow (so workflow timeline shows them).
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
                    "note": "Leave attachment",
                },
            )

        audit_svc.record(
            db,
            ctx=ctx,
            action="leave.request.create",
            entity_type="leave.leave_request",
            entity_id=leave_request_id,
            before=None,
            after={
                "leave_type_code": leave_type_code,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "unit": unit_norm,
                "requested_days": float(requested_days),
                "workflow_request_id": str(workflow_request_id),
            },
        )

        db.commit()

        # Return the created request.
        created = db.execute(
            sa.text(
                """
                SELECT
                  r.*,
                  lt.code AS leave_type_code,
                  lt.name AS leave_type_name
                FROM leave.leave_requests r
                JOIN leave.leave_types lt ON lt.id = r.leave_type_id
                WHERE r.tenant_id = :tenant_id
                  AND r.id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": leave_request_id},
        ).mappings().first()
        assert created is not None
        return dict(created)

    def cancel_my_request(self, db: Session, *, ctx: AuthContext, leave_request_id: UUID) -> dict[str, Any]:
        employee_id, tenant_id, _company_id = self.get_actor_employee_or_409(db, ctx=ctx)

        lr = db.execute(
            sa.text(
                """
                SELECT id, status, workflow_request_id, employee_id
                FROM leave.leave_requests
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": leave_request_id},
        ).mappings().first()
        if lr is None:
            raise AppError(code="leave.request.not_found", message="Leave request not found", status_code=404)
        if UUID(str(lr["employee_id"])) != employee_id:
            # Hide existence for non-requesters.
            raise AppError(code="leave.request.not_found", message="Leave request not found", status_code=404)
        if str(lr["status"]) != "PENDING":
            raise AppError(code="leave.request.not_pending", message="Leave request is not pending", status_code=409)
        if lr.get("workflow_request_id") is None:
            raise AppError(code="leave.request.not_found", message="Leave request has no workflow link", status_code=404)

        workflow_request_id = UUID(str(lr["workflow_request_id"]))

        # Cancel workflow request; domain side-effects handled via workflow hook.
        self._workflow.cancel_request(db, ctx=ctx, request_id=workflow_request_id)

        # Return updated leave request (should now be CANCELED).
        updated = db.execute(
            sa.text(
                """
                SELECT
                  r.*,
                  lt.code AS leave_type_code,
                  lt.name AS leave_type_name
                FROM leave.leave_requests r
                JOIN leave.leave_types lt ON lt.id = r.leave_type_id
                WHERE r.tenant_id = :tenant_id
                  AND r.id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": leave_request_id},
        ).mappings().first()
        assert updated is not None
        return dict(updated)

    # ------------------------------------------------------------------
    # HR admin APIs
    # ------------------------------------------------------------------
    def create_leave_type(self, db: Session, *, ctx: AuthContext, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        try:
            row = repo.insert_leave_type(db, tenant_id=tenant_id, payload=payload)
            audit_svc.record(
                db,
                ctx=ctx,
                action="leave.type.create",
                entity_type="leave.leave_type",
                entity_id=UUID(str(row["id"])),
                before=None,
                after={"code": row["code"], "name": row["name"]},
            )
            db.commit()
            return row
        except IntegrityError as e:
            db.rollback()
            raise AppError(code="validation_error", message="Leave type code already exists", status_code=409) from e

    def list_leave_types(self, db: Session, *, ctx: AuthContext, active_only: bool) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id
        return repo.list_leave_types(db, tenant_id=tenant_id, active_only=active_only)

    def create_policy(self, db: Session, *, ctx: AuthContext, payload: dict[str, Any]) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        try:
            row = repo.insert_policy(db, tenant_id=tenant_id, payload=payload)
            audit_svc.record(
                db,
                ctx=ctx,
                action="leave.policy.create",
                entity_type="leave.leave_policy",
                entity_id=UUID(str(row["id"])),
                before=None,
                after={"code": row["code"], "name": row["name"]},
            )
            db.commit()
            return row
        except IntegrityError as e:
            db.rollback()
            raise AppError(code="validation_error", message="Leave policy code already exists", status_code=409) from e

    def list_policies(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        company_id: UUID | None,
        branch_id: UUID | None,
    ) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id
        return repo.list_policies(db, tenant_id=tenant_id, company_id=company_id, branch_id=branch_id)

    def upsert_policy_rules(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        policy_id: UUID,
        rules_in: list[dict[str, Any]],
    ) -> None:
        tenant_id = ctx.scope.tenant_id
        pol = repo.get_policy_by_id(db, tenant_id=tenant_id, policy_id=policy_id)
        if pol is None:
            raise AppError(code="leave.policy.missing", message="Leave policy not found", status_code=404)

        rules: list[dict[str, Any]] = []
        for r in rules_in:
            lt = repo.get_leave_type_by_code(db, tenant_id=tenant_id, code=str(r["leave_type_code"]))
            if lt is None:
                raise AppError(code="leave.type.not_found", message="Leave type not found", status_code=404)
            rules.append(
                {
                    "leave_type_id": UUID(str(lt["id"])),
                    "annual_entitlement_days": _decimal_days(r.get("annual_entitlement_days", 0)),
                    "allow_half_day": bool(r.get("allow_half_day", False)),
                    "requires_attachment": r.get("requires_attachment"),
                }
            )

        repo.upsert_policy_rules(db, tenant_id=tenant_id, policy_id=policy_id, rules=rules)
        audit_svc.record(
            db,
            ctx=ctx,
            action="leave.policy.rules.upsert",
            entity_type="leave.leave_policy",
            entity_id=policy_id,
            before=None,
            after={"rules_count": len(rules)},
        )
        db.commit()

    def assign_employee_policy(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        employee_id: UUID,
        policy_id: UUID,
        effective_from: date,
        effective_to: date | None,
    ) -> None:
        tenant_id = ctx.scope.tenant_id

        ok_emp = db.execute(
            sa.text("SELECT 1 FROM hr_core.employees WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": employee_id, "tenant_id": tenant_id},
        ).first()
        if ok_emp is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)

        pol = repo.get_policy_by_id(db, tenant_id=tenant_id, policy_id=policy_id)
        if pol is None:
            raise AppError(code="leave.policy.missing", message="Leave policy not found", status_code=404)

        repo.assign_employee_policy(
            db,
            tenant_id=tenant_id,
            employee_id=employee_id,
            policy_id=policy_id,
            effective_from=effective_from,
            effective_to=effective_to,
        )
        audit_svc.record(
            db,
            ctx=ctx,
            action="leave.employee_policy.assign",
            entity_type="leave.employee_leave_policy",
            entity_id=employee_id,
            before=None,
            after={"policy_id": str(policy_id), "effective_from": effective_from.isoformat(), "effective_to": str(effective_to) if effective_to else None},
        )
        db.commit()

    def allocate_balance(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        employee_id: UUID,
        leave_type_code: str,
        year: int,
        days: float,
        note: str | None,
    ) -> UUID:
        tenant_id = ctx.scope.tenant_id

        lt = repo.get_leave_type_by_code(db, tenant_id=tenant_id, code=leave_type_code)
        if lt is None:
            raise AppError(code="leave.type.not_found", message="Leave type not found", status_code=404)
        leave_type_id = UUID(str(lt["id"]))

        ok_emp = db.execute(
            sa.text("SELECT 1 FROM hr_core.employees WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": employee_id, "tenant_id": tenant_id},
        ).first()
        if ok_emp is None:
            raise AppError(code="hr.employee.not_found", message="Employee not found", status_code=404)

        ledger_id = repo.insert_ledger_row(
            db,
            tenant_id=tenant_id,
            employee_id=employee_id,
            leave_type_id=leave_type_id,
            period_year=int(year),
            delta_days=_decimal_days(days),
            source_type="ALLOCATION",
            source_id=None,
            note=note,
            created_by_user_id=ctx.user_id,
            idempotent_for_leave_request=False,
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="leave.ledger.allocate",
            entity_type="leave.leave_ledger",
            entity_id=ledger_id,
            before=None,
            after={
                "employee_id": str(employee_id),
                "leave_type_code": leave_type_code,
                "period_year": int(year),
                "delta_days": float(_decimal_days(days)),
            },
        )
        db.commit()
        return ledger_id

    # ------------------------------------------------------------------
    # Calendar config
    # ------------------------------------------------------------------
    def get_weekly_off(self, db: Session, *, ctx: AuthContext, branch_id: UUID) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id
        return repo.list_weekly_off(db, tenant_id=tenant_id, branch_id=branch_id)

    def put_weekly_off(self, db: Session, *, ctx: AuthContext, branch_id: UUID, days: list[dict[str, Any]]) -> None:
        tenant_id = ctx.scope.tenant_id
        seen = {int(d["weekday"]) for d in days}
        if len(days) != 7 or seen != set(range(7)):
            raise AppError(code="validation_error", message="days must include weekdays 0..6 exactly once", status_code=400)

        ok_branch = db.execute(
            sa.text("SELECT 1 FROM tenancy.branches WHERE id = :id AND tenant_id = :tenant_id"),
            {"id": branch_id, "tenant_id": tenant_id},
        ).first()
        if ok_branch is None:
            raise AppError(code="validation_error", message="Invalid branch_id", status_code=400)

        repo.replace_weekly_off(db, tenant_id=tenant_id, branch_id=branch_id, days=days)
        audit_svc.record(
            db,
            ctx=ctx,
            action="leave.calendar.weekly_off.set",
            entity_type="leave.weekly_off",
            entity_id=branch_id,
            before=None,
            after={"branch_id": str(branch_id)},
        )
        db.commit()

    def list_holidays(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        branch_id: UUID | None,
        from_day: date | None,
        to_day: date | None,
    ) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id
        return repo.list_holidays(db, tenant_id=tenant_id, branch_id=branch_id, from_day=from_day, to_day=to_day)

    def create_holiday(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        branch_id: UUID | None,
        day: date,
        name: str,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id
        if branch_id is not None:
            ok_branch = db.execute(
                sa.text("SELECT 1 FROM tenancy.branches WHERE id = :id AND tenant_id = :tenant_id"),
                {"id": branch_id, "tenant_id": tenant_id},
            ).first()
            if ok_branch is None:
                raise AppError(code="validation_error", message="Invalid branch_id", status_code=400)

        row = repo.insert_holiday(db, tenant_id=tenant_id, branch_id=branch_id, day=day, name=name)
        audit_svc.record(
            db,
            ctx=ctx,
            action="leave.calendar.holiday.create",
            entity_type="leave.holiday",
            entity_id=UUID(str(row["id"])),
            before=None,
            after={"day": day.isoformat(), "name": name, "branch_id": str(branch_id) if branch_id else None},
        )
        db.commit()
        return row

    # ------------------------------------------------------------------
    # MSS calendar
    # ------------------------------------------------------------------
    def team_calendar(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        from_day: date,
        to_day: date,
        depth: str,
        branch_id: UUID | None,
    ) -> list[dict[str, Any]]:
        if depth not in {"1", "all"}:
            raise AppError(code="mss.invalid_depth", message="depth must be '1' or 'all'", status_code=400)

        tenant_id = ctx.scope.tenant_id
        company_id = ctx.scope.company_id
        if company_id is None:
            raise AppError(code="iam.scope.invalid_company", message="Company scope is required", status_code=400)

        actor_employee_id = db.execute(
            sa.text(
                """
                SELECT e.id
                FROM hr_core.employee_user_links l
                JOIN hr_core.employees e ON e.id = l.employee_id
                WHERE l.user_id = :user_id
                  AND e.tenant_id = :tenant_id
                  AND e.company_id = :company_id
                LIMIT 1
                """
            ),
            {"user_id": ctx.user_id, "tenant_id": tenant_id, "company_id": company_id},
        ).scalar()
        if actor_employee_id is None:
            raise AppError(code="mss.not_linked", message="User is not linked to an employee", status_code=409)
        actor_employee_id = UUID(str(actor_employee_id))

        if branch_id is not None:
            ok_branch = db.execute(
                sa.text(
                    """
                    SELECT 1
                    FROM tenancy.branches
                    WHERE id = :branch_id
                      AND tenant_id = :tenant_id
                      AND company_id = :company_id
                    """
                ),
                {"branch_id": branch_id, "tenant_id": tenant_id, "company_id": company_id},
            ).first()
            if ok_branch is None:
                raise AppError(code="validation_error", message="Invalid branch_id", status_code=400)

        subtree_sql = (
            """
            subtree AS (
              SELECT ee.employee_id, 1 AS depth
              FROM hr_core.employee_employment ee
              WHERE ee.tenant_id = :tenant_id
                AND ee.company_id = :company_id
                AND ee.end_date IS NULL
                AND ee.manager_employee_id = :actor_employee_id

              UNION ALL

              SELECT child.employee_id, s.depth + 1 AS depth
              FROM hr_core.employee_employment child
              JOIN subtree s ON child.manager_employee_id = s.employee_id
              WHERE child.tenant_id = :tenant_id
                AND child.company_id = :company_id
                AND child.end_date IS NULL
                AND s.depth < 50
            )
            """
            if depth == "all"
            else """
            subtree AS (
              SELECT ee.employee_id, 1 AS depth
              FROM hr_core.employee_employment ee
              WHERE ee.tenant_id = :tenant_id
                AND ee.company_id = :company_id
                AND ee.end_date IS NULL
                AND ee.manager_employee_id = :actor_employee_id
            )
            """
        )

        rows = db.execute(
            sa.text(
                f"""
                WITH RECURSIVE {subtree_sql}
                SELECT
                  r.id AS leave_request_id,
                  r.employee_id,
                  r.start_date,
                  r.end_date,
                  lt.code AS leave_type_code,
                  r.requested_days
                FROM leave.leave_requests r
                JOIN leave.leave_types lt ON lt.id = r.leave_type_id
                WHERE r.tenant_id = :tenant_id
                  AND r.status = 'APPROVED'
                  AND r.employee_id IN (SELECT employee_id FROM subtree)
                  AND r.start_date <= :to_day
                  AND r.end_date >= :from_day
                  AND (CAST(:branch_id AS uuid) IS NULL OR r.branch_id = :branch_id)
                ORDER BY r.start_date ASC, r.end_date ASC, r.id ASC
                """
            ),
            {
                "tenant_id": tenant_id,
                "company_id": company_id,
                "actor_employee_id": actor_employee_id,
                "from_day": from_day,
                "to_day": to_day,
                "branch_id": branch_id,
            },
        ).mappings().all()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Workflow hooks (do NOT commit here)
    # ------------------------------------------------------------------
    def _load_leave_request_for_update(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        leave_request_id: UUID,
    ) -> dict[str, Any] | None:
        row = db.execute(
            sa.text(
                """
                SELECT *
                FROM leave.leave_requests
                WHERE tenant_id = :tenant_id
                  AND id = :id
                FOR UPDATE
                """
            ),
            {"tenant_id": tenant_id, "id": leave_request_id},
        ).mappings().first()
        return dict(row) if row is not None else None

    def on_workflow_approved(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        tenant_id = ctx.scope.tenant_id
        entity_id = workflow_request.get("entity_id")
        if entity_id is None:
            return
        leave_request_id = UUID(str(entity_id))

        lr = self._load_leave_request_for_update(db, tenant_id=tenant_id, leave_request_id=leave_request_id)
        if lr is None:
            raise AppError(code="leave.request.not_found", message="Leave request not found", status_code=404)
        if str(lr["status"]) == "APPROVED":
            return
        if str(lr["status"]) != "PENDING":
            raise AppError(code="leave.request.not_pending", message="Leave request is not pending", status_code=409)

        leave_type_id = UUID(str(lr["leave_type_id"]))
        policy_id = UUID(str(lr["policy_id"]))

        pol = repo.get_policy_by_id(db, tenant_id=tenant_id, policy_id=policy_id)
        if pol is None:
            raise AppError(code="leave.policy.missing", message="Leave policy not found", status_code=400)
        year_start_month = int(pol["year_start_month"])
        period_year = _period_year(year_start_month=year_start_month, d=lr["start_date"])

        lt = db.execute(
            sa.text(
                """
                SELECT allow_negative_balance
                FROM leave.leave_types
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": leave_type_id},
        ).mappings().first()
        if lt is None:
            raise AppError(code="leave.type.not_found", message="Leave type not found", status_code=400)
        allow_negative = bool(lt["allow_negative_balance"])

        requested_days = Decimal(str(lr["requested_days"]))

        # Re-check balance at approval time (prevents approving into negative when disallowed).
        balance = repo.get_balance(
            db,
            tenant_id=tenant_id,
            employee_id=UUID(str(lr["employee_id"])),
            leave_type_id=leave_type_id,
            period_year=period_year,
        )
        if (requested_days > balance) and (not allow_negative):
            raise AppError(code="leave.insufficient_balance", message="Insufficient leave balance", status_code=409)

        ledger_id = repo.insert_ledger_row(
            db,
            tenant_id=tenant_id,
            employee_id=UUID(str(lr["employee_id"])),
            leave_type_id=leave_type_id,
            period_year=period_year,
            delta_days=(requested_days * Decimal("-1")),
            source_type="LEAVE_REQUEST",
            source_id=leave_request_id,
            note=None,
            created_by_user_id=ctx.user_id,
            idempotent_for_leave_request=True,
        )

        # Attendance overrides for countable days.
        day_rows = db.execute(
            sa.text(
                """
                SELECT day
                FROM leave.leave_request_days
                WHERE tenant_id = :tenant_id
                  AND leave_request_id = :leave_request_id
                  AND countable = true
                ORDER BY day ASC
                """
            ),
            {"tenant_id": tenant_id, "leave_request_id": leave_request_id},
        ).all()
        for (day_val,) in day_rows:
            db.execute(
                sa.text(
                    """
                    INSERT INTO attendance.day_overrides (
                      tenant_id, employee_id, branch_id, day,
                      status, source_type, source_id
                    ) VALUES (
                      :tenant_id, :employee_id, :branch_id, :day,
                      'ON_LEAVE', 'LEAVE_REQUEST', :source_id
                    )
                    ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "employee_id": UUID(str(lr["employee_id"])),
                    "branch_id": UUID(str(lr["branch_id"])),
                    "day": day_val,
                    "source_id": leave_request_id,
                },
            )

        db.execute(
            sa.text(
                """
                UPDATE leave.leave_requests
                SET status = 'APPROVED',
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": leave_request_id},
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="leave.ledger.consume",
            entity_type="leave.leave_ledger",
            entity_id=ledger_id,
            before=None,
            after={"leave_request_id": str(leave_request_id), "delta_days": float(requested_days * Decimal("-1"))},
        )
        audit_svc.record(
            db,
            ctx=ctx,
            action="leave.request.finalize",
            entity_type="leave.leave_request",
            entity_id=leave_request_id,
            before={"status": "PENDING"},
            after={"status": "APPROVED", "workflow_request_id": str(workflow_request.get("id"))},
        )

    def on_workflow_rejected(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        tenant_id = ctx.scope.tenant_id
        entity_id = workflow_request.get("entity_id")
        if entity_id is None:
            return
        leave_request_id = UUID(str(entity_id))

        lr = self._load_leave_request_for_update(db, tenant_id=tenant_id, leave_request_id=leave_request_id)
        if lr is None:
            return
        if str(lr["status"]) == "REJECTED":
            return
        if str(lr["status"]) != "PENDING":
            return

        db.execute(
            sa.text(
                """
                UPDATE leave.leave_requests
                SET status = 'REJECTED',
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": leave_request_id},
        )
        audit_svc.record(
            db,
            ctx=ctx,
            action="leave.request.finalize",
            entity_type="leave.leave_request",
            entity_id=leave_request_id,
            before={"status": "PENDING"},
            after={"status": "REJECTED", "workflow_request_id": str(workflow_request.get("id"))},
        )

    def on_workflow_cancelled(self, db: Session, *, ctx: AuthContext, workflow_request: dict[str, Any]) -> None:
        tenant_id = ctx.scope.tenant_id
        entity_id = workflow_request.get("entity_id")
        if entity_id is None:
            return
        leave_request_id = UUID(str(entity_id))

        lr = self._load_leave_request_for_update(db, tenant_id=tenant_id, leave_request_id=leave_request_id)
        if lr is None:
            return
        if str(lr["status"]) == "CANCELED":
            return
        if str(lr["status"]) != "PENDING":
            return

        db.execute(
            sa.text(
                """
                UPDATE leave.leave_requests
                SET status = 'CANCELED',
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": leave_request_id},
        )
        audit_svc.record(
            db,
            ctx=ctx,
            action="leave.request.cancel",
            entity_type="leave.leave_request",
            entity_id=leave_request_id,
            before={"status": "PENDING"},
            after={"status": "CANCELED", "workflow_request_id": str(workflow_request.get("id"))},
        )
