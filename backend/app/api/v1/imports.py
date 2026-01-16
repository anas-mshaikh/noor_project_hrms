"""
imports.py (Phase 2)

Admin Import flow:
- Admin uploads an Excel file containing two sheets: POS + Attendance
- Backend parses report-style sheets (header row detected by scanning)
- Stores normalized per-salesman summaries in Postgres (source of truth)
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

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel
import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.imports.excel import sheet_to_matrix
from app.imports.parsing import (
    ParsedWorkbook,
    RowError,
    merge_parsed,
    parse_attendance_sheet,
    parse_pos_sheet,
)
from app.models.models import (
    AttendanceSummary,
    Dataset,
    MonthState,
    PosSummary,
    Salesman,
    Store,
)
from app.mobile.repository import infer_single_store, resolve_store_org
from app.mobile.service import sync_mobile_for_dataset

router = APIRouter(tags=["imports"])
logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# Response models
# -----------------------------------------------------------------------------


class ImportCountsOut(BaseModel):
    salesmen: int
    pos_rows: int
    attendance_rows: int


class ImportErrorOut(BaseModel):
    sheet: str
    row: int
    message: str


class ImportTopSaleOut(BaseModel):
    salesman_id: str
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
    salesman_id: str
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
    for sid, pos in parsed.pos.items():
        salesman = parsed.salesmen.get(sid)
        rows.append(
            (
                float(pos.net_sales) if pos.net_sales is not None else None,
                sid,
                salesman.name if salesman else sid,
            )
        )
    rows.sort(key=lambda x: (x[0] is None, -(x[0] or 0.0)))
    for net_sales, sid, name in rows[:10]:
        top.append(ImportTopSaleOut(salesman_id=sid, name=name, net_sales=net_sales))

    return ImportPreviewOut(
        topSales=top,
        errors=[_row_error_out(e) for e in parsed.errors[:200]],
    )


def _ensure_openpyxl():
    try:
        import openpyxl  # type: ignore

        return openpyxl
    except Exception as e:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"openpyxl is required for Excel imports. Install it and retry. ({e})",
        )


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------


@router.post("/imports", response_model=ImportResponse, status_code=status.HTTP_201_CREATED)
def upload_import(
    file: UploadFile = File(...),
    month_key: str | None = Form(default=None),
    uploaded_by: str | None = Form(default=None),
    store_id: str | None = Form(default=None),
    db: Session = Depends(get_db),
) -> ImportResponse:
    # 1) Validate input
    try:
        month_key_final = _validate_month_key(month_key or _month_key_now())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    store_uuid: UUID | None = None
    if store_id:
        try:
            store_uuid = UUID(store_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="store_id must be a valid UUID",
            )
        if db.get(Store, store_uuid) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"store not found: {store_uuid}",
            )

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

    existing_all = db.execute(
        select(Dataset).where(Dataset.month_key == month_key_final, Dataset.checksum == checksum)
    ).scalars().all()

    existing: Dataset | None = None
    if store_uuid is not None:
        for cand in existing_all:
            if cand.store_id == store_uuid:
                existing = cand
                break
        if existing is None and existing_all:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="dataset already exists for this month with a different store_id",
            )
    else:
        existing = existing_all[0] if existing_all else None

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
            if store_uuid is not None:
                existing.store_id = store_uuid
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
                return ImportResponse(
                    dataset_id=existing.id,
                    month_key=existing.month_key,
                    status=existing.status,
                    sync_status=existing.sync_status,
                    counts=ImportCountsOut(salesmen=0, pos_rows=0, attendance_rows=0),
                    preview=ImportPreviewOut(
                        topSales=[],
                        errors=[ImportErrorOut(sheet="workbook", row=1, message=str(e))],
                    ),
                )

            try:
                pos_name, pos_ws, att_name, att_ws = _pick_sheets(wb)
            except ValueError as e:
                existing.status = "FAILED"
                db.add(existing)
                db.commit()
                return ImportResponse(
                    dataset_id=existing.id,
                    month_key=existing.month_key,
                    status=existing.status,
                    sync_status=existing.sync_status,
                    counts=ImportCountsOut(salesmen=0, pos_rows=0, attendance_rows=0),
                    preview=ImportPreviewOut(
                        topSales=[],
                        errors=[ImportErrorOut(sheet="workbook", row=1, message=str(e))],
                    ),
                )

            pos_matrix = sheet_to_matrix(pos_ws)
            att_matrix = sheet_to_matrix(att_ws)
            parsed_pos = parse_pos_sheet(pos_name, pos_matrix)
            parsed_att = parse_attendance_sheet(att_name, att_matrix)
            parsed = merge_parsed(parsed_pos, parsed_att)

            pos_header_failed = bool(parsed_pos.errors) and not parsed_pos.salesmen and not parsed_pos.pos
            att_header_failed = (
                bool(parsed_att.errors) and not parsed_att.salesmen and not parsed_att.attendance
            )
            if pos_header_failed or att_header_failed:
                existing.status = "FAILED"
                db.add(existing)
                db.commit()
                return ImportResponse(
                    dataset_id=existing.id,
                    month_key=existing.month_key,
                    status=existing.status,
                    sync_status=existing.sync_status,
                    counts=ImportCountsOut(salesmen=0, pos_rows=0, attendance_rows=0),
                    preview=_build_preview(parsed),
                )

            # Replace summaries for this dataset.
            db.execute(sa.delete(PosSummary).where(PosSummary.dataset_id == existing.id))
            db.execute(
                sa.delete(AttendanceSummary).where(AttendanceSummary.dataset_id == existing.id)
            )

            for sid, s in parsed.salesmen.items():
                existing_salesman = db.get(Salesman, sid)
                if existing_salesman is None:
                    db.add(Salesman(salesman_id=sid, name=s.name, department=s.department))
                else:
                    existing_salesman.name = s.name
                    if s.department:
                        existing_salesman.department = s.department
                    existing_salesman.active = True

            for sid, row in parsed.pos.items():
                db.add(
                    PosSummary(
                        dataset_id=existing.id,
                        salesman_id=sid,
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
                        dataset_id=existing.id,
                        salesman_id=sid,
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
                "imports: dataset READY (revalidated) dataset_id=%s month_key=%s salesmen=%s pos_rows=%s attendance_rows=%s errors=%s",
                existing.id,
                existing.month_key,
                len(parsed.salesmen),
                len(parsed.pos),
                len(parsed.attendance),
                len(parsed.errors),
            )

            return ImportResponse(
                dataset_id=existing.id,
                month_key=existing.month_key,
                status=existing.status,
                sync_status=existing.sync_status,
                counts=ImportCountsOut(
                    salesmen=len(parsed.salesmen),
                    pos_rows=len(parsed.pos),
                    attendance_rows=len(parsed.attendance),
                ),
                preview=_build_preview(parsed),
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
                select(sa.distinct(PosSummary.salesman_id)).where(
                    PosSummary.dataset_id == existing.id
                )
            ).scalars()
        )
        att_ids = set(
            db.execute(
                select(sa.distinct(AttendanceSummary.salesman_id)).where(
                    AttendanceSummary.dataset_id == existing.id
                )
            ).scalars()
        )
        salesman_count = len(pos_ids | att_ids)

        top_rows = db.execute(
            select(Salesman.salesman_id, Salesman.name, PosSummary.net_sales)
            .select_from(Salesman)
            .join(
                PosSummary,
                (PosSummary.salesman_id == Salesman.salesman_id)
                & (PosSummary.dataset_id == existing.id),
                isouter=True,
            )
            .order_by(PosSummary.net_sales.desc().nullslast())
            .limit(10)
        ).all()

        top_sales = [
            ImportTopSaleOut(
                salesman_id=r.salesman_id,
                name=r.name,
                net_sales=float(r.net_sales) if r.net_sales is not None else None,
            )
            for r in top_rows
            if r.net_sales is not None
        ]

        return ImportResponse(
            dataset_id=existing.id,
            month_key=existing.month_key,
            status=existing.status,
            sync_status=existing.sync_status,
            counts=ImportCountsOut(
                salesmen=int(salesman_count),
                pos_rows=int(pos_count),
                attendance_rows=int(att_count),
            ),
            preview=ImportPreviewOut(topSales=top_sales, errors=[]),
        )

    # 3) Create dataset row first (so we can track FAILED states too)
    ds = Dataset(
        id=dataset_id,
        month_key=month_key_final,
        store_id=store_uuid,
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
        # Another request likely inserted the same (month_key, checksum) dataset concurrently.
        db.rollback()
        existing2 = db.execute(
            select(Dataset).where(
                Dataset.month_key == month_key_final, Dataset.checksum == checksum
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
            return ImportResponse(
                dataset_id=existing2.id,
                month_key=existing2.month_key,
                status=existing2.status,
                sync_status=existing2.sync_status,
                counts=ImportCountsOut(salesmen=0, pos_rows=0, attendance_rows=0),
                preview=ImportPreviewOut(topSales=[], errors=[]),
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
        return ImportResponse(
            dataset_id=ds.id,
            month_key=ds.month_key,
            status=ds.status,
            sync_status=ds.sync_status,
            counts=ImportCountsOut(salesmen=0, pos_rows=0, attendance_rows=0),
            preview=ImportPreviewOut(
                topSales=[],
                errors=[ImportErrorOut(sheet="workbook", row=1, message=str(e))],
            ),
        )

    try:
        pos_name, pos_ws, att_name, att_ws = _pick_sheets(wb)
    except ValueError as e:
        ds.status = "FAILED"
        db.add(ds)
        db.commit()
        return ImportResponse(
            dataset_id=ds.id,
            month_key=ds.month_key,
            status=ds.status,
            sync_status=ds.sync_status,
            counts=ImportCountsOut(salesmen=0, pos_rows=0, attendance_rows=0),
            preview=ImportPreviewOut(
                topSales=[],
                errors=[ImportErrorOut(sheet="workbook", row=1, message=str(e))],
            ),
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
    pos_header_failed = bool(parsed_pos.errors) and not parsed_pos.salesmen and not parsed_pos.pos
    att_header_failed = (
        bool(parsed_att.errors) and not parsed_att.salesmen and not parsed_att.attendance
    )
    if pos_header_failed or att_header_failed:
        ds.status = "FAILED"
        db.add(ds)
        db.commit()
        return ImportResponse(
            dataset_id=ds.id,
            month_key=ds.month_key,
            status=ds.status,
            sync_status=ds.sync_status,
            counts=ImportCountsOut(salesmen=0, pos_rows=0, attendance_rows=0),
            preview=_build_preview(parsed),
        )

    # 5) Upsert salesmen
    for sid, s in parsed.salesmen.items():
        existing_salesman = db.get(Salesman, sid)
        if existing_salesman is None:
            db.add(Salesman(salesman_id=sid, name=s.name, department=s.department))
        else:
            existing_salesman.name = s.name
            if s.department:
                existing_salesman.department = s.department
            existing_salesman.active = True

    # 6) Insert summaries
    for sid, row in parsed.pos.items():
        db.add(
            PosSummary(
                dataset_id=ds.id,
                salesman_id=sid,
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
                dataset_id=ds.id,
                salesman_id=sid,
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
        "imports: dataset READY dataset_id=%s month_key=%s salesmen=%s pos_rows=%s attendance_rows=%s errors=%s",
        ds.id,
        ds.month_key,
        len(parsed.salesmen),
        len(parsed.pos),
        len(parsed.attendance),
        len(parsed.errors),
    )

    return ImportResponse(
        dataset_id=ds.id,
        month_key=ds.month_key,
        status=ds.status,
        sync_status=ds.sync_status,
        counts=ImportCountsOut(
            salesmen=len(parsed.salesmen),
            pos_rows=len(parsed.pos),
            attendance_rows=len(parsed.attendance),
        ),
        preview=_build_preview(parsed),
    )


@router.post("/imports/{dataset_id}/publish", response_model=PublishResponse)
def publish_import(dataset_id: UUID, db: Session = Depends(get_db)) -> PublishResponse:
    ds = db.get(Dataset, dataset_id)
    if ds is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="dataset not found")
    if ds.status != "READY":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"dataset status must be READY to publish (got {ds.status})",
        )

    # Update month_state (source of truth pointer)
    ms = db.get(MonthState, ds.month_key)
    if ms is None:
        ms = MonthState(month_key=ds.month_key, published_dataset_id=ds.id)
        db.add(ms)
    else:
        ms.published_dataset_id = ds.id

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
        return PublishResponse(
            month_key=ds.month_key, published_dataset_id=ds.id, sync_status=ds.sync_status
        )

    ds.sync_status = "PENDING"
    db.add(ds)
    db.commit()
    logger.info(
        "imports: publish started dataset_id=%s month_key=%s sync=PENDING",
        ds.id,
        ds.month_key,
    )

    store_id = ds.store_id
    if store_id is None:
        # Safe fallback: only infer a store when there is exactly one in the system.
        inferred_store = infer_single_store(db)
        if inferred_store is not None:
            store_id = inferred_store.id
            ds.store_id = store_id
            db.add(ds)
            db.commit()
            logger.info(
                "mobile sync: inferred store_id=%s for dataset_id=%s",
                store_id,
                ds.id,
            )
    if store_id is None:
        # Publish is still allowed, but we mark sync as failed so it can be retried later.
        ds.sync_status = "FAILED"
        db.add(ds)
        db.commit()
        logger.warning(
            "mobile sync skipped: dataset_id=%s month_key=%s store_id missing",
            ds.id,
            ds.month_key,
        )
        return PublishResponse(
            month_key=ds.month_key, published_dataset_id=ds.id, sync_status=ds.sync_status
        )

    try:
        store, org = resolve_store_org(db, store_id)
        sync_mobile_for_dataset(
            db,
            dataset=ds,
            month_key=ds.month_key,
            store_id=store.id,
            org_id=org.id,
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Mobile sync failed: {e}",
        )

    db.add(ds)
    db.commit()
    return PublishResponse(
        month_key=ds.month_key, published_dataset_id=ds.id, sync_status=ds.sync_status
    )


@router.get("/months/{month_key}/leaderboard", response_model=list[LeaderboardRowOut])
def leaderboard(month_key: str, db: Session = Depends(get_db)) -> list[LeaderboardRowOut]:
    ms = db.get(MonthState, month_key)
    if ms is None or ms.published_dataset_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="month not published")

    dataset_id = ms.published_dataset_id

    q = (
        select(
            Salesman.salesman_id,
            Salesman.name,
            Salesman.department,
            PosSummary.qty,
            PosSummary.net_sales,
            PosSummary.bills,
            PosSummary.customers,
            PosSummary.return_customers,
            AttendanceSummary.present,
            AttendanceSummary.absent,
            AttendanceSummary.work_minutes,
            AttendanceSummary.stocking_done,
            AttendanceSummary.stocking_missed,
        )
        .select_from(Salesman)
        .join(
            PosSummary,
            (PosSummary.salesman_id == Salesman.salesman_id) & (PosSummary.dataset_id == dataset_id),
            isouter=True,
        )
        .join(
            AttendanceSummary,
            (AttendanceSummary.salesman_id == Salesman.salesman_id)
            & (AttendanceSummary.dataset_id == dataset_id),
            isouter=True,
        )
    )

    rows = db.execute(q).all()

    def net_sales_key(r: Any) -> tuple[bool, float]:
        ns = float(r.net_sales) if r.net_sales is not None else 0.0
        return (r.net_sales is None, -ns)

    rows_sorted = sorted(rows, key=net_sales_key)
    out: list[LeaderboardRowOut] = []
    for r in rows_sorted:
        out.append(
            LeaderboardRowOut(
                salesman_id=r.salesman_id,
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
    return out
