"""
Payrun compute and read services (Milestone 9).

Payruns materialize payroll-ready outputs into immutable payrun_items and
payrun_item_lines so UI/reporting reads are fast and deterministic.

Key properties (v1):
- Deterministic computation from (compensation + payable summaries).
- Idempotent generation using DB uniqueness and row locks.
- Batch queries (no per-employee DB calls).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any, Iterable
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.domains.payroll.utils import json_canonical, money, to_decimal, utcnow
from app.shared.types import AuthContext


@dataclass(frozen=True)
class PeriodInfo:
    """Small container for period identifiers and inclusive range."""

    period_id: UUID
    period_key: str
    start_date: date
    end_date: date


def _as_uuid(value) -> UUID:
    return UUID(str(value))


def _require_branch_id(ctx: AuthContext, branch_id: UUID | None) -> UUID:
    if branch_id is None:
        raise AppError(code="iam.scope.invalid_branch", message="branch_id is required", status_code=400)
    return branch_id


class PayrunService:
    """Generate and read payruns (payroll.payruns + items/lines)."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_payrun(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        calendar_id: UUID,
        period_key: str,
        branch_id: UUID | None,
        idempotency_key: str | None,
    ) -> dict[str, Any]:
        """
        Generate a payrun (idempotent).

        v1 behavior:
        - One payrun per (tenant, period_id, branch_id, version=1).
        - If a payrun already exists, return it without recomputing unless it
          is DRAFT and has no items (retry after partial failure).
        """

        if not idempotency_key:
            raise AppError(code="validation_error", message="idempotency_key is required", status_code=400)

        tenant_id = ctx.scope.tenant_id

        cal = self._require_calendar(db, tenant_id=tenant_id, calendar_id=calendar_id)
        period = self._require_period(db, tenant_id=tenant_id, calendar_id=calendar_id, period_key=period_key)

        # Branch scoping: payruns are effectively branch-scoped in v1.
        active_branch_id = ctx.scope.branch_id
        if branch_id is not None and active_branch_id is not None and branch_id != active_branch_id:
            raise AppError(code="iam.scope.mismatch", message="branch_id does not match active scope", status_code=400)

        branch_id_final = _require_branch_id(ctx, branch_id or active_branch_id)

        # Try to find an existing payrun for this (period, branch, version=1).
        existing = (
            db.execute(
                sa.text(
                    """
                    SELECT *
                    FROM payroll.payruns
                    WHERE tenant_id = :tenant_id
                      AND period_id = :period_id
                      AND branch_id = :branch_id
                      AND version = 1
                    ORDER BY created_at DESC, id DESC
                    LIMIT 1
                    """
                ),
                {"tenant_id": tenant_id, "period_id": period.period_id, "branch_id": branch_id_final},
            )
            .mappings()
            .first()
        )
        if existing is not None:
            # Retry safety: if items are missing (e.g., crash between payrun row
            # insert and item insert), recompute under a row lock.
            if str(existing["status"]) == "DRAFT":
                items_count = int(
                    db.execute(
                        sa.text(
                            """
                            SELECT count(*)
                            FROM payroll.payrun_items
                            WHERE tenant_id = :tenant_id
                              AND payrun_id = :payrun_id
                            """
                        ),
                        {"tenant_id": tenant_id, "payrun_id": existing["id"]},
                    ).scalar()
                    or 0
                )
                if items_count == 0:
                    self._compute_payrun_items(
                        db,
                        ctx=ctx,
                        payrun_id=_as_uuid(existing["id"]),
                        cal=cal,
                        period=period,
                        branch_id=branch_id_final,
                    )
                    # Audit once per successful recompute attempt.
                    audit_svc.record(
                        db,
                        ctx=ctx,
                        action="payroll.payrun.generate",
                        entity_type="payroll.payrun",
                        entity_id=_as_uuid(existing["id"]),
                        before=None,
                        after={
                            "calendar_id": str(calendar_id),
                            "period_key": str(period.period_key),
                            "branch_id": str(branch_id_final),
                            "note": "recompute_missing_items",
                        },
                    )
                    db.commit()

            return self.get_payrun(db, ctx=ctx, payrun_id=_as_uuid(existing["id"]), include_lines=False)["payrun"]

        # Create the payrun row, handling races via unique constraints.
        try:
            payrun_row = (
                db.execute(
                    sa.text(
                        """
                        INSERT INTO payroll.payruns (
                          tenant_id,
                          calendar_id,
                          period_id,
                          branch_id,
                          version,
                          status,
                          generated_by_user_id,
                          idempotency_key
                        ) VALUES (
                          :tenant_id,
                          :calendar_id,
                          :period_id,
                          :branch_id,
                          1,
                          'DRAFT',
                          :generated_by_user_id,
                          :idempotency_key
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "calendar_id": calendar_id,
                        "period_id": period.period_id,
                        "branch_id": branch_id_final,
                        "generated_by_user_id": ctx.user_id,
                        "idempotency_key": idempotency_key,
                    },
                )
                .mappings()
                .first()
            )
            assert payrun_row is not None
            payrun_id = _as_uuid(payrun_row["id"])
        except IntegrityError:
            # Another transaction created the payrun concurrently.
            db.rollback()
            row = (
                db.execute(
                    sa.text(
                        """
                        SELECT *
                        FROM payroll.payruns
                        WHERE tenant_id = :tenant_id
                          AND period_id = :period_id
                          AND branch_id = :branch_id
                          AND version = 1
                        ORDER BY created_at DESC, id DESC
                        LIMIT 1
                        """
                    ),
                    {"tenant_id": tenant_id, "period_id": period.period_id, "branch_id": branch_id_final},
                )
                .mappings()
                .first()
            )
            if row is None:
                raise AppError(
                    code="payroll.payrun.generate.failed",
                    message="Failed to create payrun",
                    status_code=500,
                )
            payrun_id = _as_uuid(row["id"])

        # Compute items/lines deterministically.
        self._compute_payrun_items(
            db,
            ctx=ctx,
            payrun_id=payrun_id,
            cal=cal,
            period=period,
            branch_id=branch_id_final,
        )

        audit_svc.record(
            db,
            ctx=ctx,
            action="payroll.payrun.generate",
            entity_type="payroll.payrun",
            entity_id=payrun_id,
            before=None,
            after={
                "calendar_id": str(calendar_id),
                "period_key": str(period.period_key),
                "branch_id": str(branch_id_final),
            },
        )

        db.commit()
        return self.get_payrun(db, ctx=ctx, payrun_id=payrun_id, include_lines=False)["payrun"]

    def get_payrun(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        payrun_id: UUID,
        include_lines: bool,
    ) -> dict[str, Any]:
        """
        Return a payrun detail (admin only).

        Scope hardening:
        - If the caller has an active branch scope, require the payrun.branch_id
          matches it. Return 404 on mismatch to avoid cross-branch leaks.
        """

        tenant_id = ctx.scope.tenant_id
        payrun = self._require_payrun_row(db, tenant_id=tenant_id, payrun_id=payrun_id, ctx_branch_id=ctx.scope.branch_id)

        items = (
            db.execute(
                sa.text(
                    """
                    SELECT *
                    FROM payroll.payrun_items
                    WHERE tenant_id = :tenant_id
                      AND payrun_id = :payrun_id
                    ORDER BY employee_id ASC, id ASC
                    """
                ),
                {"tenant_id": tenant_id, "payrun_id": payrun_id},
            )
            .mappings()
            .all()
        )
        items_list = [dict(r) for r in items]

        lines_list: list[dict[str, Any]] | None = None
        if include_lines:
            lines = (
                db.execute(
                    sa.text(
                        """
                        SELECT l.*
                        FROM payroll.payrun_item_lines l
                        JOIN payroll.payrun_items i
                          ON i.id = l.payrun_item_id
                         AND i.tenant_id = l.tenant_id
                        WHERE l.tenant_id = :tenant_id
                          AND i.payrun_id = :payrun_id
                        ORDER BY i.employee_id ASC, l.created_at ASC, l.id ASC
                        """
                    ),
                    {"tenant_id": tenant_id, "payrun_id": payrun_id},
                )
                .mappings()
                .all()
            )
            lines_list = [dict(r) for r in lines]

        return {"payrun": dict(payrun), "items": items_list, "lines": lines_list}

    # ------------------------------------------------------------------
    # Internal: compute engine
    # ------------------------------------------------------------------
    def _compute_payrun_items(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        payrun_id: UUID,
        cal: dict[str, Any],
        period: PeriodInfo,
        branch_id: UUID,
    ) -> None:
        """
        Compute payrun items/lines under a payrun row lock.

        Concurrency:
        - We lock the payrun row FOR UPDATE to serialize compute vs submit/publish.
        - We delete existing items (DRAFT only) to keep inserts idempotent and
          prevent duplicate line items (payrun_item_lines has no unique key).
        """

        tenant_id = ctx.scope.tenant_id

        locked = (
            db.execute(
                sa.text(
                    """
                    SELECT id, status
                    FROM payroll.payruns
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                    FOR UPDATE
                    """
                ),
                {"tenant_id": tenant_id, "id": payrun_id},
            )
            .mappings()
            .first()
        )
        if locked is None:
            raise AppError(code="payroll.payrun.not_found", message="Payrun not found", status_code=404)
        if str(locked["status"]) != "DRAFT":
            raise AppError(
                code="payroll.payrun.invalid_state",
                message="Payrun is not editable",
                status_code=409,
            )

        # Reset derived outputs for idempotent recompute.
        db.execute(
            sa.text(
                """
                DELETE FROM payroll.payrun_items
                WHERE tenant_id = :tenant_id
                  AND payrun_id = :payrun_id
                """
            ),
            {"tenant_id": tenant_id, "payrun_id": payrun_id},
        )

        employees = self._list_employees_in_branch(db, tenant_id=tenant_id, branch_id=branch_id)
        employee_ids = [e["employee_id"] for e in employees]

        # If no employees, keep totals empty and return.
        if not employee_ids:
            self._update_payrun_totals(
                db,
                tenant_id=tenant_id,
                payrun_id=payrun_id,
                totals={
                    "included_count": 0,
                    "excluded_count": 0,
                    "gross_total": "0.00",
                    "deductions_total": "0.00",
                    "net_total": "0.00",
                    "currency_code": str(cal["currency_code"]),
                },
            )
            return

        comp_by_emp = self._load_effective_compensations(
            db,
            tenant_id=tenant_id,
            employee_ids=employee_ids,
            as_of=period.start_date,
        )

        payable_by_emp = self._load_payable_aggregates(
            db,
            tenant_id=tenant_id,
            branch_id=branch_id,
            employee_ids=employee_ids,
            from_day=period.start_date,
            to_day=period.end_date,
        )

        structure_ids: set[UUID] = set()
        for comp in comp_by_emp.values():
            structure_ids.add(_as_uuid(comp["salary_structure_id"]))

        lines_by_structure = self._load_structure_lines(
            db, tenant_id=tenant_id, structure_ids=sorted(list(structure_ids))
        )

        calendar_currency = str(cal["currency_code"])

        item_rows: list[dict[str, Any]] = []
        line_rows: list[dict[str, Any]] = []

        included_count = 0
        excluded_count = 0
        gross_total = Decimal("0")
        deductions_total = Decimal("0")
        net_total = Decimal("0")

        for emp in employees:
            employee_id: UUID = emp["employee_id"]
            employee_code: str | None = emp.get("employee_code")

            comp = comp_by_emp.get(employee_id)
            payable = payable_by_emp.get(employee_id)

            anomalies: list[str] = []
            status = "INCLUDED"

            if comp is None:
                status = "EXCLUDED"
                anomalies.append("NO_COMPENSATION")
            if payable is None:
                status = "EXCLUDED"
                anomalies.append("NO_PAYABLE_SUMMARIES")
            if comp is not None and str(comp["currency_code"]) != calendar_currency:
                status = "EXCLUDED"
                anomalies.append("CURRENCY_MISMATCH")

            payable_days = int(payable["payable_days"]) if payable is not None else 0
            working_days_in_period = int(payable["working_days_in_period"]) if payable is not None else 0
            payable_minutes = int(payable["payable_minutes"]) if payable is not None else 0

            gross_amount = Decimal("0")
            deductions_amount = Decimal("0")
            net_amount = Decimal("0")
            computed: dict[str, Any] = {
                "employee_code": employee_code,
                "period_key": period.period_key,
                "currency_code": calendar_currency,
                "inputs": {
                    "payable_days": payable_days,
                    "working_days_in_period": working_days_in_period,
                    "payable_minutes": payable_minutes,
                },
                "anomalies": anomalies,
            }

            payrun_item_id = uuid4()

            if status == "INCLUDED" and comp is not None and payable is not None:
                base_amount = to_decimal(comp["base_amount"], default=Decimal("0")) or Decimal("0")
                # v1 proration: payable_days / max(working_days_in_period, 1).
                denom = max(int(working_days_in_period), 1)
                proration_factor = Decimal(int(payable_days)) / Decimal(int(denom))
                prorated_base = money(base_amount * proration_factor)

                structure_id = _as_uuid(comp["salary_structure_id"])
                struct_lines = lines_by_structure.get(structure_id, [])

                # First pass: compute FIXED/MANUAL lines to build percent base.
                fixed_earnings_total = Decimal("0")
                earnings_total_amt = Decimal("0")
                deductions_total_amt = Decimal("0")

                staged: list[dict[str, Any]] = []
                for ln in struct_lines:
                    comp_type = str(ln["component_type"])
                    comp_code = str(ln["component_code"])
                    calc_mode = str(ln["calc_mode_override"] or ln["component_calc_mode"])

                    if calc_mode == "PERCENT_OF_GROSS":
                        staged.append({"kind": "PERCENT", "ln": ln})
                        continue

                    amount = Decimal("0")
                    meta: dict[str, Any] | None = None

                    if calc_mode == "FIXED":
                        amt = to_decimal(ln.get("amount_override"))
                        if amt is None:
                            amt = to_decimal(ln.get("default_amount"), default=Decimal("0")) or Decimal("0")
                        amount = money(amt)
                        meta = {"calc_mode": "FIXED"}
                    elif calc_mode == "MANUAL":
                        amount = Decimal("0")
                        meta = {"calc_mode": "MANUAL", "note": "manual components are 0 in v1"}
                    else:
                        # Defensive: DB CHECK should prevent unknown values.
                        amount = Decimal("0")
                        meta = {"calc_mode": str(calc_mode), "note": "unsupported calc_mode (v1)"}

                    if comp_type == "EARNING":
                        earnings_total_amt += amount
                        if calc_mode == "FIXED":
                            fixed_earnings_total += amount
                    else:
                        deductions_total_amt += amount

                    line_rows.append(
                        {
                            "id": uuid4(),
                            "tenant_id": tenant_id,
                            "payrun_item_id": payrun_item_id,
                            "component_id": _as_uuid(ln["component_id"]),
                            "component_code": comp_code,
                            "component_type": comp_type,
                            "amount": amount,
                            "meta_json": meta or {},
                        }
                    )

                percent_base_gross = prorated_base + fixed_earnings_total

                # Second pass: compute percent-of-gross lines (order-independent base).
                for s in staged:
                    ln = s["ln"]
                    comp_type = str(ln["component_type"])
                    comp_code = str(ln["component_code"])

                    pct = to_decimal(ln.get("percent_override"))
                    if pct is None:
                        pct = to_decimal(ln.get("default_percent"), default=Decimal("0")) or Decimal("0")
                    pct_val = Decimal(pct)
                    amount = money(percent_base_gross * (pct_val / Decimal("100")))

                    if comp_type == "EARNING":
                        earnings_total_amt += amount
                    else:
                        deductions_total_amt += amount

                    line_rows.append(
                        {
                            "id": uuid4(),
                            "tenant_id": tenant_id,
                            "payrun_item_id": payrun_item_id,
                            "component_id": _as_uuid(ln["component_id"]),
                            "component_code": comp_code,
                            "component_type": comp_type,
                            "amount": amount,
                            "meta_json": {"calc_mode": "PERCENT_OF_GROSS", "percent": str(pct_val)},
                        }
                    )

                gross_amount = money(prorated_base + earnings_total_amt)
                deductions_amount = money(deductions_total_amt)
                net_amount = money(gross_amount - deductions_amount)

                computed["inputs"].update(
                    {
                        "base_amount": str(money(base_amount)),
                        "proration_factor": str(proration_factor),
                        "prorated_base": str(prorated_base),
                        "percent_base_gross": str(money(percent_base_gross)),
                    }
                )
                computed["totals"] = {
                    "gross_amount": str(gross_amount),
                    "deductions_amount": str(deductions_amount),
                    "net_amount": str(net_amount),
                }

            anomalies_json: dict[str, Any] | None = None
            if anomalies:
                anomalies_json = {"codes": anomalies}

            item_rows.append(
                {
                    "id": payrun_item_id,
                    "tenant_id": tenant_id,
                    "payrun_id": payrun_id,
                    "employee_id": employee_id,
                    "payable_days": int(payable_days),
                    "payable_minutes": int(payable_minutes),
                    "working_days_in_period": int(working_days_in_period),
                    "gross_amount": gross_amount,
                    "deductions_amount": deductions_amount,
                    "net_amount": net_amount,
                    "status": status,
                    "computed_json": computed,
                    "anomalies_json": anomalies_json,
                }
            )

            if status == "INCLUDED":
                included_count += 1
                gross_total += gross_amount
                deductions_total += deductions_amount
                net_total += net_amount
            else:
                excluded_count += 1

        # Bulk insert items.
        if item_rows:
            db.execute(
                sa.text(
                    """
                    INSERT INTO payroll.payrun_items (
                      id,
                      tenant_id,
                      payrun_id,
                      employee_id,
                      payable_days,
                      payable_minutes,
                      working_days_in_period,
                      gross_amount,
                      deductions_amount,
                      net_amount,
                      status,
                      computed_json,
                      anomalies_json
                    ) VALUES (
                      :id,
                      :tenant_id,
                      :payrun_id,
                      :employee_id,
                      :payable_days,
                      :payable_minutes,
                      :working_days_in_period,
                      :gross_amount,
                      :deductions_amount,
                      :net_amount,
                      :status,
                      CAST(:computed_json AS jsonb),
                      CAST(:anomalies_json AS jsonb)
                    )
                    """
                ),
                [
                    {
                        **r,
                        "computed_json": json_canonical(r["computed_json"]),
                        "anomalies_json": json_canonical(r["anomalies_json"]) if r["anomalies_json"] is not None else None,
                    }
                    for r in item_rows
                ],
            )

        # Bulk insert lines.
        if line_rows:
            db.execute(
                sa.text(
                    """
                    INSERT INTO payroll.payrun_item_lines (
                      id,
                      tenant_id,
                      payrun_item_id,
                      component_id,
                      component_code,
                      component_type,
                      amount,
                      meta_json
                    ) VALUES (
                      :id,
                      :tenant_id,
                      :payrun_item_id,
                      :component_id,
                      :component_code,
                      :component_type,
                      :amount,
                      CAST(:meta_json AS jsonb)
                    )
                    """
                ),
                [
                    {
                        **r,
                        "meta_json": json_canonical(r.get("meta_json") or {}),
                    }
                    for r in line_rows
                ],
            )

        self._update_payrun_totals(
            db,
            tenant_id=tenant_id,
            payrun_id=payrun_id,
            totals={
                "included_count": int(included_count),
                "excluded_count": int(excluded_count),
                "gross_total": str(money(gross_total)),
                "deductions_total": str(money(deductions_total)),
                "net_total": str(money(net_total)),
                "currency_code": calendar_currency,
                "computed_at": utcnow().isoformat(),
            },
        )

    # ------------------------------------------------------------------
    # Internal: shared queries
    # ------------------------------------------------------------------
    def _require_calendar(self, db: Session, *, tenant_id: UUID, calendar_id: UUID) -> dict[str, Any]:
        row = (
            db.execute(
                sa.text(
                    """
                    SELECT *
                    FROM payroll.calendars
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                    """
                ),
                {"tenant_id": tenant_id, "id": calendar_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(code="payroll.calendar.not_found", message="Calendar not found", status_code=404)
        return dict(row)

    def _require_period(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        calendar_id: UUID,
        period_key: str,
    ) -> PeriodInfo:
        row = (
            db.execute(
                sa.text(
                    """
                    SELECT id, period_key, start_date, end_date
                    FROM payroll.periods
                    WHERE tenant_id = :tenant_id
                      AND calendar_id = :calendar_id
                      AND period_key = :period_key
                    """
                ),
                {"tenant_id": tenant_id, "calendar_id": calendar_id, "period_key": period_key},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(code="payroll.period.not_found", message="Period not found", status_code=404)
        return PeriodInfo(
            period_id=_as_uuid(row["id"]),
            period_key=str(row["period_key"]),
            start_date=row["start_date"],
            end_date=row["end_date"],
        )

    def _require_payrun_row(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        payrun_id: UUID,
        ctx_branch_id: UUID | None,
        for_update: bool = False,
    ) -> sa.RowMapping:
        lock = "FOR UPDATE" if for_update else ""
        row = (
            db.execute(
                sa.text(
                    f"""
                    SELECT *
                    FROM payroll.payruns
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                    {lock}
                    """
                ),
                {"tenant_id": tenant_id, "id": payrun_id},
            )
            .mappings()
            .first()
        )
        if row is None:
            raise AppError(code="payroll.payrun.not_found", message="Payrun not found", status_code=404)

        if ctx_branch_id is not None:
            payrun_branch = row.get("branch_id")
            if payrun_branch is None or _as_uuid(payrun_branch) != ctx_branch_id:
                # Participant-safe: hide cross-branch existence.
                raise AppError(code="payroll.payrun.not_found", message="Payrun not found", status_code=404)

        return row

    def _list_employees_in_branch(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        branch_id: UUID,
    ) -> list[dict[str, Any]]:
        rows = (
            db.execute(
                sa.text(
                    """
                    SELECT employee_id, employee_code
                    FROM hr_core.v_employee_current_employment
                    WHERE tenant_id = :tenant_id
                      AND branch_id = :branch_id
                      AND status = 'ACTIVE'
                    ORDER BY employee_id ASC
                    """
                ),
                {"tenant_id": tenant_id, "branch_id": branch_id},
            )
            .mappings()
            .all()
        )
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "employee_id": _as_uuid(r["employee_id"]),
                    "employee_code": str(r["employee_code"]) if r.get("employee_code") is not None else None,
                }
            )
        return out

    def _load_effective_compensations(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        employee_ids: list[UUID],
        as_of: date,
    ) -> dict[UUID, dict[str, Any]]:
        rows = (
            db.execute(
                sa.text(
                    """
                    SELECT DISTINCT ON (employee_id)
                      employee_id,
                      currency_code,
                      salary_structure_id,
                      base_amount,
                      effective_from,
                      effective_to
                    FROM payroll.employee_compensations
                    WHERE tenant_id = :tenant_id
                      AND employee_id = ANY(CAST(:employee_ids AS uuid[]))
                      AND effective_from <= :as_of
                      AND (effective_to IS NULL OR effective_to >= :as_of)
                    ORDER BY employee_id, effective_from DESC, created_at DESC, id DESC
                    """
                ),
                {"tenant_id": tenant_id, "employee_ids": list(employee_ids), "as_of": as_of},
            )
            .mappings()
            .all()
        )
        out: dict[UUID, dict[str, Any]] = {}
        for r in rows:
            out[_as_uuid(r["employee_id"])] = dict(r)
        return out

    def _load_payable_aggregates(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        employee_ids: list[UUID],
        from_day: date,
        to_day: date,
    ) -> dict[UUID, dict[str, Any]]:
        rows = (
            db.execute(
                sa.text(
                    """
                    SELECT
                      employee_id,
                      COUNT(*) FILTER (WHERE day_type = 'WORKDAY') AS working_days_in_period,
                      COUNT(*) FILTER (WHERE day_type = 'WORKDAY' AND presence_status = 'PRESENT') AS payable_days,
                      COALESCE(SUM(payable_minutes), 0) AS payable_minutes
                    FROM attendance.payable_day_summaries
                    WHERE tenant_id = :tenant_id
                      AND branch_id = :branch_id
                      AND employee_id = ANY(CAST(:employee_ids AS uuid[]))
                      AND day BETWEEN :from_day AND :to_day
                    GROUP BY employee_id
                    """
                ),
                {
                    "tenant_id": tenant_id,
                    "branch_id": branch_id,
                    "employee_ids": list(employee_ids),
                    "from_day": from_day,
                    "to_day": to_day,
                },
            )
            .mappings()
            .all()
        )
        out: dict[UUID, dict[str, Any]] = {}
        for r in rows:
            out[_as_uuid(r["employee_id"])] = dict(r)
        return out

    def _load_structure_lines(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        structure_ids: list[UUID],
    ) -> dict[UUID, list[dict[str, Any]]]:
        if not structure_ids:
            return {}

        rows = (
            db.execute(
                sa.text(
                    """
                    SELECT
                      l.salary_structure_id,
                      l.component_id,
                      l.sort_order,
                      l.calc_mode_override,
                      l.amount_override,
                      l.percent_override,
                      c.code AS component_code,
                      c.component_type,
                      c.calc_mode AS component_calc_mode,
                      c.default_amount,
                      c.default_percent
                    FROM payroll.salary_structure_lines l
                    JOIN payroll.components c
                      ON c.id = l.component_id
                     AND c.tenant_id = l.tenant_id
                    WHERE l.tenant_id = :tenant_id
                      AND l.salary_structure_id = ANY(CAST(:structure_ids AS uuid[]))
                    ORDER BY l.salary_structure_id ASC, l.sort_order ASC, l.created_at ASC, l.id ASC
                    """
                ),
                {"tenant_id": tenant_id, "structure_ids": list(structure_ids)},
            )
            .mappings()
            .all()
        )

        out: dict[UUID, list[dict[str, Any]]] = {}
        for r in rows:
            sid = _as_uuid(r["salary_structure_id"])
            out.setdefault(sid, []).append(dict(r))
        return out

    def _update_payrun_totals(
        self,
        db: Session,
        *,
        tenant_id: UUID,
        payrun_id: UUID,
        totals: dict[str, Any],
    ) -> None:
        db.execute(
            sa.text(
                """
                UPDATE payroll.payruns
                SET totals_json = CAST(:totals AS jsonb),
                    updated_at = now()
                WHERE tenant_id = :tenant_id
                  AND id = :id
                """
            ),
            {"tenant_id": tenant_id, "id": payrun_id, "totals": json_canonical(totals)},
        )

