"""
Shift template service (Milestone 8).

This service owns CRUD for `roster.shift_templates` and encapsulates:
- Overnight shift handling (end_time <= start_time means "ends next day")
- Break validation (break_minutes must not exceed duration)

We intentionally keep the data model simple in v1; richer policy rules (late,
grace windows, min-full-day, overtime) will be layered on top later.
"""

from __future__ import annotations

from datetime import time
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit import service as audit_svc
from app.core.errors import AppError
from app.shared.types import AuthContext


def compute_shift_minutes(*, start_time: time, end_time: time, break_minutes: int) -> int:
    """
    Compute expected work minutes for a shift template.

    Overnight rule:
    - If end_time <= start_time, we treat end_time as "next day".

    Validation:
    - start_time == end_time is rejected in v1 to avoid ambiguous 24h shifts.
    - break_minutes must be <= duration_minutes.
    """

    start_m = int(start_time.hour) * 60 + int(start_time.minute)
    end_m = int(end_time.hour) * 60 + int(end_time.minute)

    if start_m == end_m:
        raise AppError(
            code="roster.shift.invalid_time_range",
            message="start_time and end_time cannot be equal",
            status_code=400,
        )

    # Overnight shifts are supported: end wraps to next day.
    if end_m <= start_m:
        end_m += 24 * 60

    duration = end_m - start_m

    if break_minutes < 0 or break_minutes > duration:
        raise AppError(
            code="roster.shift.break_invalid",
            message="break_minutes must be between 0 and shift duration",
            status_code=400,
        )

    expected = duration - int(break_minutes)
    return max(int(expected), 0)


class ShiftTemplateService:
    """CRUD for roster.shift_templates (branch-scoped)."""

    # ------------------------------------------------------------------
    # Create
    # ------------------------------------------------------------------
    def create_shift_template(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        branch_id: UUID,
        code: str,
        name: str,
        start_time: time,
        end_time: time,
        break_minutes: int,
        grace_minutes: int,
        min_full_day_minutes: int | None,
        is_active: bool,
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id

        expected = compute_shift_minutes(
            start_time=start_time,
            end_time=end_time,
            break_minutes=int(break_minutes),
        )

        # Placeholder validation: if a minimum full-day minutes threshold is set,
        # it must fit within the computed shift minutes.
        if min_full_day_minutes is not None and int(min_full_day_minutes) > expected:
            raise AppError(
                code="roster.shift.break_invalid",
                message="min_full_day_minutes must be <= expected shift minutes",
                status_code=400,
            )

        try:
            row = (
                db.execute(
                    sa.text(
                        """
                        INSERT INTO roster.shift_templates (
                          tenant_id, branch_id,
                          code, name,
                          start_time, end_time,
                          break_minutes,
                          grace_minutes,
                          min_full_day_minutes,
                          is_active,
                          created_by_user_id
                        ) VALUES (
                          :tenant_id, :branch_id,
                          :code, :name,
                          :start_time, :end_time,
                          :break_minutes,
                          :grace_minutes,
                          :min_full_day_minutes,
                          :is_active,
                          :created_by_user_id
                        )
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "branch_id": branch_id,
                        "code": code,
                        "name": name,
                        "start_time": start_time,
                        "end_time": end_time,
                        "break_minutes": int(break_minutes),
                        "grace_minutes": int(grace_minutes),
                        "min_full_day_minutes": int(min_full_day_minutes)
                        if min_full_day_minutes is not None
                        else None,
                        "is_active": bool(is_active),
                        "created_by_user_id": ctx.user_id,
                    },
                )
                .mappings()
                .first()
            )
            assert row is not None

            audit_svc.record(
                db,
                ctx=ctx,
                action="roster.shift.create",
                entity_type="roster.shift_template",
                entity_id=UUID(str(row["id"])),
                before=None,
                after={
                    "branch_id": str(branch_id),
                    "code": code,
                    "name": name,
                    "start_time": str(start_time),
                    "end_time": str(end_time),
                    "break_minutes": int(break_minutes),
                    "expected_minutes": int(expected),
                    "is_active": bool(is_active),
                },
            )

            db.commit()
        except IntegrityError as e:
            db.rollback()
            # Most common: (tenant, branch, code) uniqueness violation.
            raise AppError(
                code="validation_error",
                message="Shift template code already exists for the branch",
                status_code=409,
            ) from e
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

        out = dict(row)
        out["expected_minutes"] = int(expected)
        return out

    # ------------------------------------------------------------------
    # List
    # ------------------------------------------------------------------
    def list_shift_templates(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        branch_id: UUID,
        active_only: bool,
    ) -> list[dict[str, Any]]:
        tenant_id = ctx.scope.tenant_id

        where = ["tenant_id = :tenant_id", "branch_id = :branch_id"]
        params: dict[str, Any] = {"tenant_id": tenant_id, "branch_id": branch_id}
        if active_only:
            where.append("is_active = true")

        sql = f"""
            SELECT *
            FROM roster.shift_templates
            WHERE {" AND ".join(where)}
            ORDER BY is_active DESC, code ASC, created_at ASC, id ASC
        """
        rows = db.execute(sa.text(sql), params).mappings().all()
        items: list[dict[str, Any]] = []
        for r in rows:
            expected = compute_shift_minutes(
                start_time=r["start_time"],
                end_time=r["end_time"],
                break_minutes=int(r["break_minutes"] or 0),
            )
            d = dict(r)
            d["expected_minutes"] = int(expected)
            items.append(d)
        return items

    # ------------------------------------------------------------------
    # Patch
    # ------------------------------------------------------------------
    def patch_shift_template(
        self,
        db: Session,
        *,
        ctx: AuthContext,
        shift_template_id: UUID,
        patch: dict[str, Any],
    ) -> dict[str, Any]:
        tenant_id = ctx.scope.tenant_id

        existing = (
            db.execute(
                sa.text(
                    """
                    SELECT *
                    FROM roster.shift_templates
                    WHERE tenant_id = :tenant_id
                      AND id = :id
                    """
                ),
                {"tenant_id": tenant_id, "id": shift_template_id},
            )
            .mappings()
            .first()
        )
        if existing is None:
            raise AppError(
                code="roster.shift.not_found",
                message="Shift template not found",
                status_code=404,
            )

        # Merge patch with current values so our validation sees the final shape.
        merged: dict[str, Any] = dict(existing)
        for k, v in patch.items():
            if v is not None:
                merged[k] = v

        expected = compute_shift_minutes(
            start_time=merged["start_time"],
            end_time=merged["end_time"],
            break_minutes=int(merged["break_minutes"] or 0),
        )
        if merged.get("min_full_day_minutes") is not None and int(merged["min_full_day_minutes"]) > expected:
            raise AppError(
                code="roster.shift.break_invalid",
                message="min_full_day_minutes must be <= expected shift minutes",
                status_code=400,
            )

        before = {
            "code": str(existing["code"]),
            "name": str(existing["name"]),
            "start_time": str(existing["start_time"]),
            "end_time": str(existing["end_time"]),
            "break_minutes": int(existing["break_minutes"] or 0),
            "grace_minutes": int(existing["grace_minutes"] or 0),
            "min_full_day_minutes": existing.get("min_full_day_minutes"),
            "is_active": bool(existing["is_active"]),
        }

        try:
            updated = (
                db.execute(
                    sa.text(
                        """
                        UPDATE roster.shift_templates
                        SET
                          code = :code,
                          name = :name,
                          start_time = :start_time,
                          end_time = :end_time,
                          break_minutes = :break_minutes,
                          grace_minutes = :grace_minutes,
                          min_full_day_minutes = :min_full_day_minutes,
                          is_active = :is_active
                        WHERE tenant_id = :tenant_id
                          AND id = :id
                        RETURNING *
                        """
                    ),
                    {
                        "tenant_id": tenant_id,
                        "id": shift_template_id,
                        "code": merged["code"],
                        "name": merged["name"],
                        "start_time": merged["start_time"],
                        "end_time": merged["end_time"],
                        "break_minutes": int(merged["break_minutes"] or 0),
                        "grace_minutes": int(merged["grace_minutes"] or 0),
                        "min_full_day_minutes": merged.get("min_full_day_minutes"),
                        "is_active": bool(merged["is_active"]),
                    },
                )
                .mappings()
                .first()
            )
            assert updated is not None

            audit_svc.record(
                db,
                ctx=ctx,
                action="roster.shift.patch",
                entity_type="roster.shift_template",
                entity_id=shift_template_id,
                before=before,
                after={
                    "code": str(updated["code"]),
                    "name": str(updated["name"]),
                    "start_time": str(updated["start_time"]),
                    "end_time": str(updated["end_time"]),
                    "break_minutes": int(updated["break_minutes"] or 0),
                    "expected_minutes": int(expected),
                    "is_active": bool(updated["is_active"]),
                },
            )
            db.commit()
        except IntegrityError as e:
            db.rollback()
            raise AppError(
                code="validation_error",
                message="Shift template code already exists for the branch",
                status_code=409,
            ) from e
        except AppError:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            raise

        out = dict(updated)
        out["expected_minutes"] = int(expected)
        return out

