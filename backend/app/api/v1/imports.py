"""
imports.py (Phase 2)

Admin Import flow:
- Admin uploads an Excel file containing two sheets: POS + Attendance
- Backend parses report-style sheets (header row detected by scanning)
- Stores normalized per-employee summaries in Postgres (source of truth)
- Optional: sync mobile-ready data to Firebase Firestore (new namespace)

This module is intentionally self-contained and does NOT change existing routes.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from pydantic import BaseModel
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import require_permission
from app.auth.permissions import IMPORTS_READ, IMPORTS_WRITE, MOBILE_SYNC
from app.core.config import settings
from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.imports.excel import sheet_to_matrix
from app.imports.parsing import (
    ParsedEmployee,
    ParsedWorkbook,
    RowError,
    merge_parsed,
    parse_attendance_sheet,
    parse_pos_sheet,
)
from app.models.models import AttendanceSummary, Dataset, MonthState, PosSummary
from app.mobile.service import sync_mobile_for_dataset
from app.shared.types import AuthContext

router = APIRouter(tags=["imports"])
logger = logging.getLogger(__name__)

def _ok_model(model: BaseModel) -> dict[str, object]:
    return ok(model.model_dump())


# -----------------------------------------------------------------------------
# Response models
# -----------------------------------------------------------------------------


class ImportCountsOut(BaseModel):
    employees: int
    pos_rows: int
    attendance_rows: int


class ImportErrorOut(BaseModel):
    sheet: str
    row: int
    message: str


class ImportTopSaleOut(BaseModel):
    employee_code: str
    name: str
    net_sales: float | None


class ImportPreviewOut(BaseModel):
    topSales: list[ImportTopSaleOut]
    errors: list[ImportErrorOut]


class ImportResponse(BaseModel):
    dataset_id: UUID
    month_key: str
    status: str
    sync_status: str
    counts: ImportCountsOut
    preview: ImportPreviewOut


class PublishResponse(BaseModel):
    month_key: str
    published_dataset_id: UUID
    sync_status: str


class LeaderboardRowOut(BaseModel):
    employee_id: UUID
    employee_code: str
    name: str
    department: str | None = None

    qty: float | None = None
    net_sales: float | None = None
    bills: int | None = None
    customers: int | None = None
    return_customers: int | None = None

    present: int | None = None
    absent: int | None = None
    work_minutes: int | None = None
    stocking_done: int | None = None
    stocking_missed: int | None = None


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------


def _month_key_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m")


def _validate_month_key(month_key: str) -> str:
    month_key = (month_key or "").strip()
    if not month_key:
        raise ValueError("month_key is required")
    # Very small validator: YYYY-MM
    if len(month_key) != 7 or month_key[4] != "-":
        raise ValueError("month_key must be in YYYY-MM format")
    yyyy, mm = month_key.split("-", 1)
    if not (yyyy.isdigit() and mm.isdigit()):
        raise ValueError("month_key must be in YYYY-MM format")
    if not (1 <= int(mm) <= 12):
        raise ValueError("month_key must be in YYYY-MM format")
    return month_key


def _sha256_and_write(upload: UploadFile, dest_path: Path) -> tuple[str, int]:
    """
    Stream the uploaded file to disk while computing sha256.
    """
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = dest_path.with_suffix(dest_path.suffix + ".part")

    h = hashlib.sha256()
    total = 0

    with tmp_path.open("wb") as f:
        while True:
            chunk = upload.file.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            h.update(chunk)
            f.write(chunk)

    tmp_path.replace(dest_path)
    return (h.hexdigest(), total)


def _pick_sheets(wb: Any) -> tuple[str, Any, str, Any]:
    """
    Determine which sheets are POS + Attendance.

    Rules:
    1) Prefer sheet names containing "pos" and "attend" (case-insensitive).
    2) Otherwise, if workbook has >=2 sheets, take first two.
    """
    sheets = list(getattr(wb, "worksheets", []))
    if len(sheets) < 2:
        raise ValueError("Workbook must contain at least 2 sheets (POS + Attendance)")

    def find_by_token(token: str) -> Any | None:
        token = token.lower()
        for ws in sheets:
            name = str(getattr(ws, "title", "")).lower()
            if token in name:
                return ws
        return None

    pos_ws = find_by_token("pos")
    att_ws = find_by_token("attend")

    if pos_ws is not None and att_ws is not None and pos_ws is not att_ws:
        return (str(pos_ws.title), pos_ws, str(att_ws.title), att_ws)

    # Fallback: first two sheets
    return (str(sheets[0].title), sheets[0], str(sheets[1].title), sheets[1])


def _row_error_out(err: RowError) -> ImportErrorOut:
    return ImportErrorOut(sheet=err.sheet, row=err.row, message=err.message)


def _build_preview(parsed: ParsedWorkbook) -> ImportPreviewOut:
    top: list[ImportTopSaleOut] = []

    # Order by net_sales desc, nulls last.
    rows = []
    for code, pos in parsed.pos.items():
        employee = parsed.employees.get(code)
        rows.append(
            (
                float(pos.net_sales) if pos.net_sales is not None else None,
                code,
                employee.name if employee else code,
            )
        )
    rows.sort(key=lambda x: (x[0] is None, -(x[0] or 0.0)))
    for net_sales, code, name in rows[:10]:
        top.append(ImportTopSaleOut(employee_code=code, name=name, net_sales=net_sales))

    return ImportPreviewOut(
        topSales=top,
        errors=[_row_error_out(e) for e in parsed.errors[:200]],
    )


def _resolve_employee_ids_for_branch(
    db: Session,
    *,
    tenant_id: UUID,
    company_id: UUID,
    branch_id: UUID,
    employees: dict[str, ParsedEmployee],
) -> tuple[dict[str, UUID], list[str]]:
    """
    Resolve employee_code -> hr_core.employees.id for the given branch.

    Imports are not allowed to create legacy employees. Employee identity lives
    in hr_core; to import POS/Attendance data you must first create employees
    (and their active employment) in the branch.
    """
    if not employees:
        return {}, []

    codes = sorted({c.strip() for c in employees.keys() if c.strip()})
    if not codes:
        return {}, []

    sql = (
        sa.text(
            """
            WITH current_employment AS (
              SELECT
                ee.employee_id,
                ee.branch_id,
                ROW_NUMBER() OVER (
                  PARTITION BY ee.employee_id
                  ORDER BY ee.is_primary DESC NULLS LAST, ee.start_date DESC, ee.id DESC
                ) AS rn
              FROM hr_core.employee_employment ee
              WHERE ee.tenant_id = :tenant_id
                AND ee.company_id = :company_id
                AND ee.end_date IS NULL
            ),
            ce AS (
              SELECT * FROM current_employment WHERE rn = 1
            )
            SELECT e.id AS employee_id, e.employee_code
            FROM hr_core.employees e
            JOIN ce ON ce.employee_id = e.id
            WHERE e.tenant_id = :tenant_id
              AND e.company_id = :company_id
              AND e.employee_code IN :codes
              AND ce.branch_id = :branch_id
              AND e.status = 'ACTIVE'
            """
        )
        .bindparams(sa.bindparam("codes", expanding=True))
    )

    rows = db.execute(
        sql,
        {
            "tenant_id": tenant_id,
            "company_id": company_id,
            "branch_id": branch_id,
            "codes": codes,
        },
    ).all()

    found = {str(r.employee_code): r.employee_id for r in rows}
    missing = [c for c in codes if c not in found]
    return found, missing


def _ensure_openpyxl():
    try:
        import openpyxl  # type: ignore

        return openpyxl
    except Exception as e:  # pragma: no cover
        raise AppError(
            code="vision.dependencies.missing",
            message="openpyxl is required for Excel imports",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from e


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@router.post("/branches/{branch_id}/imports", status_code=status.HTTP_201_CREATED)
def upload_import(
    branch_id: UUID,
    file: UploadFile = File(...),
    month_key: str | None = Form(default=None),
    uploaded_by: str | None = Form(default=None),
    ctx: AuthContext = Depends(require_permission(IMPORTS_WRITE)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    # 1) Validate input
    try:
        month_key_final = _validate_month_key(month_key or _month_key_now())
    except ValueError as e:
        raise AppError(code="validation_error", message=str(e), status_code=status.HTTP_422_UNPROCESSABLE_ENTITY) from e

    company_id = ctx.scope.company_id
    if company_id is None:
        raise AppError(code="iam.scope.invalid_company", message="Company scope required", status_code=400)

    # 2) Compute checksum + dedupe (idempotent per month)
    dataset_id = uuid4()
    upload_dir = Path(settings.upload_dir).resolve()
    dest_path = upload_dir / f"{dataset_id}.xlsx"

    # We need checksum before deciding idempotent; compute it while writing to disk.
    checksum, _bytes = _sha256_and_write(file, dest_path)
    logger.info(
        "imports: received upload month_key=%s bytes=%s sha256=%s path=%s",
        month_key_final,
        _bytes,
        checksum,
        dest_path,
    )

    existing = (
        db.execute(
            select(Dataset).where(
                Dataset.tenant_id == ctx.scope.tenant_id,
                Dataset.branch_id == branch_id,
                Dataset.month_key == month_key_final,
                Dataset.checksum == checksum,
            )
        )
        .scalars()
        .one_or_none()
    )

    if existing is not None:
        # If a previous upload FAILED, allow re-upload to re-validate the same dataset_id.
        # This preserves idempotency (same month_key + checksum -> same dataset_id) while
        # letting us fix parser bugs and retry without manual DB cleanup.
        if (
            existing.status == "FAILED"
            and settings.imports_revalidate_failed_on_reupload
        ):
            logger.info(
                "imports: revalidating FAILED dataset month_key=%s dataset_id=%s",
                existing.month_key,
                existing.id,
            )

            stable_path = upload_dir / f"{existing.id}.xlsx"
            stable_path.parent.mkdir(parents=True, exist_ok=True)

            # Remove any prior raw file (best-effort) and replace with the newly uploaded one.
            try:
                if existing.raw_file_path:
                    old_path = Path(existing.raw_file_path)
                    if old_path.exists() and old_path.resolve() != stable_path.resolve():
                        old_path.unlink(missing_ok=True)
            except Exception:
                pass
            try:
                stable_path.unlink(missing_ok=True)
            except Exception:
                pass
            dest_path.replace(stable_path)

            existing.raw_file_path = str(stable_path)
            if uploaded_by:
                existing.uploaded_by = uploaded_by
            existing.status = "VALIDATING"
            existing.sync_status = "DISABLED"
            db.add(existing)
            db.commit()

            openpyxl = _ensure_openpyxl()
            try:
                wb = openpyxl.load_workbook(stable_path, data_only=True)
            except Exception as e:
                existing.status = "FAILED"
                db.add(existing)
                db.commit()
                return _ok_model(
                    ImportResponse(
                        dataset_id=existing.id,
                        month_key=existing.month_key,
                        status=existing.status,
                        sync_status=existing.sync_status,
                        counts=ImportCountsOut(employees=0, pos_rows=0, attendance_rows=0),
                        preview=ImportPreviewOut(
                            topSales=[],
                            errors=[
                                ImportErrorOut(sheet="workbook", row=1, message=str(e))
                            ],
                        ),
                    )
                )

            try:
                pos_name, pos_ws, att_name, att_ws = _pick_sheets(wb)
            except ValueError as e:
                existing.status = "FAILED"
                db.add(existing)
                db.commit()
                return _ok_model(
                    ImportResponse(
                        dataset_id=existing.id,
                        month_key=existing.month_key,
                        status=existing.status,
                        sync_status=existing.sync_status,
                        counts=ImportCountsOut(employees=0, pos_rows=0, attendance_rows=0),
                        preview=ImportPreviewOut(
                            topSales=[],
                            errors=[
                                ImportErrorOut(sheet="workbook", row=1, message=str(e))
                            ],
                        ),
                    )
                )

            pos_matrix = sheet_to_matrix(pos_ws)
            att_matrix = sheet_to_matrix(att_ws)
            parsed_pos = parse_pos_sheet(pos_name, pos_matrix)
            parsed_att = parse_attendance_sheet(att_name, att_matrix)
            parsed = merge_parsed(parsed_pos, parsed_att)

            pos_header_failed = bool(parsed_pos.errors) and not parsed_pos.employees and not parsed_pos.pos
            att_header_failed = (
                bool(parsed_att.errors) and not parsed_att.employees and not parsed_att.attendance
            )
            if pos_header_failed or att_header_failed:
                existing.status = "FAILED"
                db.add(existing)
                db.commit()
                return _ok_model(
                    ImportResponse(
                        dataset_id=existing.id,
                        month_key=existing.month_key,
                        status=existing.status,
                        sync_status=existing.sync_status,
                        counts=ImportCountsOut(employees=0, pos_rows=0, attendance_rows=0),
                        preview=_build_preview(parsed),
                    )
                )

            # Replace summaries for this dataset.
            db.execute(sa.delete(PosSummary).where(PosSummary.dataset_id == existing.id))
            db.execute(
                sa.delete(AttendanceSummary).where(AttendanceSummary.dataset_id == existing.id)
            )

            employee_ids, missing_codes = _resolve_employee_ids_for_branch(
                db,
                tenant_id=ctx.scope.tenant_id,
                company_id=company_id,
                branch_id=branch_id,
                employees=parsed.employees,
            )
            if missing_codes:
                for code in missing_codes:
                    parsed.errors.append(
                        RowError(
                            sheet="employees",
                            row=1,
                            message=f"Unknown employee_code {code!r} for this branch; create the employee in HR first.",
                        )
                    )
                existing.status = "FAILED"
                db.add(existing)
                db.commit()
                return _ok_model(
                    ImportResponse(
                        dataset_id=existing.id,
                        month_key=existing.month_key,
                        status=existing.status,
                        sync_status=existing.sync_status,
                        counts=ImportCountsOut(employees=0, pos_rows=0, attendance_rows=0),
                        preview=_build_preview(parsed),
                    )
                )

            for sid, row in parsed.pos.items():
                db.add(
                    PosSummary(
                        tenant_id=ctx.scope.tenant_id,
                        dataset_id=existing.id,
                        employee_id=employee_ids[sid],
                        qty=row.qty,
                        net_sales=row.net_sales,
                        bills=row.bills,
                        customers=row.customers,
                        return_customers=row.return_customers,
                    )
                )

            for sid, row in parsed.attendance.items():
                db.add(
                    AttendanceSummary(
                        tenant_id=ctx.scope.tenant_id,
                        dataset_id=existing.id,
                        employee_id=employee_ids[sid],
                        present=row.present,
                        absent=row.absent,
                        work_minutes=row.work_minutes,
                        stocking_done=row.stocking_done,
                        stocking_missed=row.stocking_missed,
                    )
                )

            existing.status = "READY"
            db.add(existing)
            db.commit()
            logger.info(
                "imports: dataset READY (revalidated) dataset_id=%s month_key=%s employees=%s pos_rows=%s attendance_rows=%s errors=%s",
                existing.id,
                existing.month_key,
                len(parsed.employees),
                len(parsed.pos),
                len(parsed.attendance),
                len(parsed.errors),
            )

            return _ok_model(
                ImportResponse(
                    dataset_id=existing.id,
                    month_key=existing.month_key,
                    status=existing.status,
                    sync_status=existing.sync_status,
                    counts=ImportCountsOut(
                        employees=len(parsed.employees),
                        pos_rows=len(parsed.pos),
                        attendance_rows=len(parsed.attendance),
                    ),
                    preview=_build_preview(parsed),
                )
            )

        # Otherwise: dedupe and return the stored dataset as-is.
        # Keep disk tidy by removing the newly written file.
        try:
            dest_path.unlink(missing_ok=True)  # py3.8+: missing_ok
        except Exception:
            pass

        pos_count = db.execute(
            select(sa.func.count())
            .select_from(PosSummary)
            .where(PosSummary.dataset_id == existing.id)
        ).scalar_one()
        att_count = db.execute(
            select(sa.func.count())
            .select_from(AttendanceSummary)
            .where(AttendanceSummary.dataset_id == existing.id)
        ).scalar_one()
        pos_ids = set(
            db.execute(
                select(sa.distinct(PosSummary.employee_id)).where(
                    PosSummary.dataset_id == existing.id
                )
            ).scalars()
        )
        att_ids = set(
            db.execute(
                select(sa.distinct(AttendanceSummary.employee_id)).where(
                    AttendanceSummary.dataset_id == existing.id
                )
            ).scalars()
        )
        employee_count = len(pos_ids | att_ids)

        top_rows = db.execute(
            sa.text(
                """
                SELECT
                  e.employee_code AS employee_code,
                  (p.first_name || ' ' || p.last_name) AS name,
                  ps.net_sales AS net_sales
                FROM analytics.pos_summary ps
                JOIN hr_core.employees e ON e.id = ps.employee_id
                JOIN hr_core.persons p ON p.id = e.person_id
                WHERE ps.dataset_id = :dataset_id
                ORDER BY ps.net_sales DESC NULLS LAST
                LIMIT 10
                """
            ),
            {"dataset_id": existing.id},
        ).all()

        top_sales = [
            ImportTopSaleOut(
                employee_code=r.employee_code,
                name=r.name,
                net_sales=float(r.net_sales) if r.net_sales is not None else None,
            )
            for r in top_rows
            if r.net_sales is not None
        ]

        return _ok_model(
            ImportResponse(
                dataset_id=existing.id,
                month_key=existing.month_key,
                status=existing.status,
                sync_status=existing.sync_status,
                counts=ImportCountsOut(
                    employees=int(employee_count),
                    pos_rows=int(pos_count),
                    attendance_rows=int(att_count),
                ),
                preview=ImportPreviewOut(topSales=top_sales, errors=[]),
            )
        )

    # 3) Create dataset row first (so we can track FAILED states too)
    ds = Dataset(
        id=dataset_id,
        month_key=month_key_final,
        tenant_id=ctx.scope.tenant_id,
        branch_id=branch_id,
        uploaded_by=uploaded_by,
        status="VALIDATING",
        sync_status="DISABLED",
        raw_file_path=str(dest_path),
        checksum=checksum,
    )
    db.add(ds)
    try:
        db.commit()
    except IntegrityError:
        # Another request likely inserted the same (tenant_id, branch_id, month_key, checksum)
        # dataset concurrently.
        db.rollback()
        existing2 = db.execute(
            select(Dataset).where(
                Dataset.tenant_id == ctx.scope.tenant_id,
                Dataset.branch_id == branch_id,
                Dataset.month_key == month_key_final,
                Dataset.checksum == checksum,
            )
        ).scalar_one_or_none()
        if existing2 is not None:
            try:
                dest_path.unlink(missing_ok=True)
            except Exception:
                pass
            logger.info(
                "imports: deduped concurrent upload month_key=%s dataset_id=%s",
                month_key_final,
                existing2.id,
            )
            return _ok_model(
                ImportResponse(
                    dataset_id=existing2.id,
                    month_key=existing2.month_key,
                    status=existing2.status,
                    sync_status=existing2.sync_status,
                    counts=ImportCountsOut(employees=0, pos_rows=0, attendance_rows=0),
                    preview=ImportPreviewOut(topSales=[], errors=[]),
                )
            )
        raise

    # 4) Parse workbook
    openpyxl = _ensure_openpyxl()
    try:
        wb = openpyxl.load_workbook(dest_path, data_only=True)
    except Exception as e:
        ds.status = "FAILED"
        db.add(ds)
        db.commit()
        return _ok_model(
            ImportResponse(
                dataset_id=ds.id,
                month_key=ds.month_key,
                status=ds.status,
                sync_status=ds.sync_status,
                counts=ImportCountsOut(employees=0, pos_rows=0, attendance_rows=0),
                preview=ImportPreviewOut(
                    topSales=[],
                    errors=[ImportErrorOut(sheet="workbook", row=1, message=str(e))],
                ),
            )
        )

    try:
        pos_name, pos_ws, att_name, att_ws = _pick_sheets(wb)
    except ValueError as e:
        ds.status = "FAILED"
        db.add(ds)
        db.commit()
        return _ok_model(
            ImportResponse(
                dataset_id=ds.id,
                month_key=ds.month_key,
                status=ds.status,
                sync_status=ds.sync_status,
                counts=ImportCountsOut(employees=0, pos_rows=0, attendance_rows=0),
                preview=ImportPreviewOut(
                    topSales=[],
                    errors=[ImportErrorOut(sheet="workbook", row=1, message=str(e))],
                ),
            )
        )

    logger.info(
        "imports: sheets pos=%s rows=%s cols=%s | attendance=%s rows=%s cols=%s",
        pos_name,
        getattr(pos_ws, "max_row", None),
        getattr(pos_ws, "max_column", None),
        att_name,
        getattr(att_ws, "max_row", None),
        getattr(att_ws, "max_column", None),
    )

    pos_matrix = sheet_to_matrix(pos_ws)
    att_matrix = sheet_to_matrix(att_ws)

    parsed_pos = parse_pos_sheet(pos_name, pos_matrix)
    parsed_att = parse_attendance_sheet(att_name, att_matrix)
    parsed = merge_parsed(parsed_pos, parsed_att)

    # If either sheet failed header detection, treat as FAILED.
    pos_header_failed = bool(parsed_pos.errors) and not parsed_pos.employees and not parsed_pos.pos
    att_header_failed = (
        bool(parsed_att.errors) and not parsed_att.employees and not parsed_att.attendance
    )
    if pos_header_failed or att_header_failed:
        ds.status = "FAILED"
        db.add(ds)
        db.commit()
        return _ok_model(
            ImportResponse(
                dataset_id=ds.id,
                month_key=ds.month_key,
                status=ds.status,
                sync_status=ds.sync_status,
                counts=ImportCountsOut(employees=0, pos_rows=0, attendance_rows=0),
                preview=_build_preview(parsed),
            )
        )

    # 5) Resolve employee ids (HR core is the canonical employee identity).
    employee_ids, missing_codes = _resolve_employee_ids_for_branch(
        db,
        tenant_id=ctx.scope.tenant_id,
        company_id=company_id,
        branch_id=branch_id,
        employees=parsed.employees,
    )
    if missing_codes:
        for code in missing_codes:
            parsed.errors.append(
                RowError(
                    sheet="employees",
                    row=1,
                    message=f"Unknown employee_code {code!r} for this branch; create the employee in HR first.",
                )
            )
        ds.status = "FAILED"
        db.add(ds)
        db.commit()
        return _ok_model(
            ImportResponse(
                dataset_id=ds.id,
                month_key=ds.month_key,
                status=ds.status,
                sync_status=ds.sync_status,
                counts=ImportCountsOut(employees=0, pos_rows=0, attendance_rows=0),
                preview=_build_preview(parsed),
            )
        )

    # 6) Insert summaries
    for sid, row in parsed.pos.items():
        db.add(
            PosSummary(
                tenant_id=ctx.scope.tenant_id,
                dataset_id=ds.id,
                employee_id=employee_ids[sid],
                qty=row.qty,
                net_sales=row.net_sales,
                bills=row.bills,
                customers=row.customers,
                return_customers=row.return_customers,
            )
        )

    for sid, row in parsed.attendance.items():
        db.add(
            AttendanceSummary(
                tenant_id=ctx.scope.tenant_id,
                dataset_id=ds.id,
                employee_id=employee_ids[sid],
                present=row.present,
                absent=row.absent,
                work_minutes=row.work_minutes,
                stocking_done=row.stocking_done,
                stocking_missed=row.stocking_missed,
            )
        )

    ds.status = "READY"
    db.add(ds)
    db.commit()
    logger.info(
        "imports: dataset READY dataset_id=%s month_key=%s employees=%s pos_rows=%s attendance_rows=%s errors=%s",
        ds.id,
        ds.month_key,
        len(parsed.employees),
        len(parsed.pos),
        len(parsed.attendance),
        len(parsed.errors),
    )

    return _ok_model(
        ImportResponse(
            dataset_id=ds.id,
            month_key=ds.month_key,
            status=ds.status,
            sync_status=ds.sync_status,
            counts=ImportCountsOut(
                employees=len(parsed.employees),
                pos_rows=len(parsed.pos),
                attendance_rows=len(parsed.attendance),
            ),
            preview=_build_preview(parsed),
        )
    )


@router.post("/branches/{branch_id}/imports/{dataset_id}/publish")
def publish_import(
    branch_id: UUID,
    dataset_id: UUID,
    ctx: AuthContext = Depends(require_permission(MOBILE_SYNC)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ds = (
        db.query(Dataset)
        .filter(
            Dataset.id == dataset_id,
            Dataset.tenant_id == ctx.scope.tenant_id,
            Dataset.branch_id == branch_id,
        )
        .one_or_none()
    )
    if ds is None:
        raise AppError(code="vision.import.dataset.not_found", message="Dataset not found", status_code=404)
    if ds.status != "READY":
        raise AppError(
            code="vision.import.invalid_state",
            message=f"dataset status must be READY to publish (got {ds.status})",
            status_code=status.HTTP_409_CONFLICT,
        )

    # Update month_state (source of truth pointer)
    ms = (
        db.query(MonthState)
        .filter(
            MonthState.tenant_id == ctx.scope.tenant_id,
            MonthState.branch_id == branch_id,
            MonthState.month_key == ds.month_key,
        )
        .one_or_none()
    )
    if ms is None:
        ms = MonthState(
            tenant_id=ctx.scope.tenant_id,
            branch_id=branch_id,
            month_key=ds.month_key,
            published_dataset_id=ds.id,
        )
    else:
        ms.published_dataset_id = ds.id
    db.add(ms)

    # Mobile sync is the only Firestore integration now.
    if not settings.mobile_sync_enabled:
        ds.sync_status = "DISABLED"
        db.add(ds)
        db.commit()
        logger.info(
            "imports: published dataset_id=%s month_key=%s sync=DISABLED",
            ds.id,
            ds.month_key,
        )
        return _ok_model(
            PublishResponse(
                month_key=ds.month_key,
                published_dataset_id=ds.id,
                sync_status=ds.sync_status,
            )
        )

    ds.sync_status = "PENDING"
    db.add(ds)
    db.commit()
    logger.info(
        "imports: publish started dataset_id=%s month_key=%s sync=PENDING",
        ds.id,
        ds.month_key,
    )

    try:
        sync_mobile_for_dataset(
            db,
            dataset=ds,
            month_key=ds.month_key,
            tenant_id=ctx.scope.tenant_id,
            branch_id=branch_id,
            dry_run=settings.mobile_sync_dry_run,
        )
        ds.sync_status = "SYNCED"
    except Exception as e:
        ds.sync_status = "FAILED"
        db.add(ds)
        db.commit()
        logger.exception(
            "mobile sync failed dataset_id=%s month_key=%s",
            ds.id,
            ds.month_key,
        )
        raise AppError(
            code="vision.import.mobile_sync_failed",
            message="Mobile sync failed",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from e

    db.add(ds)
    db.commit()
    return _ok_model(
        PublishResponse(
            month_key=ds.month_key,
            published_dataset_id=ds.id,
            sync_status=ds.sync_status,
        )
    )


@router.get("/branches/{branch_id}/months/{month_key}/leaderboard")
def leaderboard(
    branch_id: UUID,
    month_key: str,
    ctx: AuthContext = Depends(require_permission(IMPORTS_READ)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    ms = (
        db.query(MonthState)
        .filter(
            MonthState.tenant_id == ctx.scope.tenant_id,
            MonthState.branch_id == branch_id,
            MonthState.month_key == month_key,
        )
        .one_or_none()
    )
    if ms is None or ms.published_dataset_id is None:
        raise AppError(
            code="vision.import.month_not_published",
            message="Month not published",
            status_code=status.HTTP_404_NOT_FOUND,
        )

    dataset_id = ms.published_dataset_id

    out: list[LeaderboardRowOut] = []
    rows = db.execute(
        sa.text(
            """
            WITH ids AS (
              SELECT employee_id FROM analytics.pos_summary WHERE dataset_id = :dataset_id
              UNION
              SELECT employee_id FROM attendance.attendance_summary WHERE dataset_id = :dataset_id
            ),
            current_employment AS (
              SELECT
                ee.employee_id,
                ee.branch_id,
                ee.org_unit_id,
                ROW_NUMBER() OVER (
                  PARTITION BY ee.employee_id
                  ORDER BY ee.is_primary DESC NULLS LAST, ee.start_date DESC, ee.id DESC
                ) AS rn
              FROM hr_core.employee_employment ee
              WHERE ee.tenant_id = :tenant_id
                AND ee.end_date IS NULL
            ),
            ce AS (
              SELECT * FROM current_employment WHERE rn = 1
            )
            SELECT
              e.id AS employee_id,
              e.employee_code AS employee_code,
              (p.first_name || ' ' || p.last_name) AS name,
              ou.name AS department,
              ps.qty,
              ps.net_sales,
              ps.bills,
              ps.customers,
              ps.return_customers,
              att.present,
              att.absent,
              att.work_minutes,
              att.stocking_done,
              att.stocking_missed
            FROM ids
            JOIN hr_core.employees e ON e.id = ids.employee_id
            JOIN hr_core.persons p ON p.id = e.person_id
            LEFT JOIN analytics.pos_summary ps
              ON ps.dataset_id = :dataset_id
             AND ps.employee_id = ids.employee_id
            LEFT JOIN attendance.attendance_summary att
              ON att.dataset_id = :dataset_id
             AND att.employee_id = ids.employee_id
            LEFT JOIN ce ON ce.employee_id = e.id AND ce.branch_id = :branch_id
            LEFT JOIN tenancy.org_units ou ON ou.id = ce.org_unit_id
            WHERE e.tenant_id = :tenant_id
            ORDER BY ps.net_sales DESC NULLS LAST, e.employee_code
            """
        ),
        {
            "dataset_id": dataset_id,
            "tenant_id": ctx.scope.tenant_id,
            "branch_id": branch_id,
        },
    ).all()

    for r in rows:
        out.append(
            LeaderboardRowOut(
                employee_id=r.employee_id,
                employee_code=r.employee_code,
                name=r.name,
                department=r.department,
                qty=float(r.qty) if r.qty is not None else None,
                net_sales=float(r.net_sales) if r.net_sales is not None else None,
                bills=r.bills,
                customers=r.customers,
                return_customers=r.return_customers,
                present=r.present,
                absent=r.absent,
                work_minutes=r.work_minutes,
                stocking_done=r.stocking_done,
                stocking_missed=r.stocking_missed,
            )
        )
    return ok([x.model_dump() for x in out])
