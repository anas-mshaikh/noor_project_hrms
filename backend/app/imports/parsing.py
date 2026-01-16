from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import time, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable


# -----------------------------------------------------------------------------
# Types
# -----------------------------------------------------------------------------


@dataclass(frozen=True)
class RowError:
    sheet: str
    row: int  # 1-based Excel row number
    message: str


@dataclass
class ParsedSalesman:
    salesman_id: str
    name: str
    department: str | None = None


@dataclass
class ParsedPosSummary:
    salesman_id: str
    qty: Decimal | None = None
    net_sales: Decimal | None = None
    bills: int | None = None
    customers: int | None = None
    return_customers: int | None = None


@dataclass
class ParsedAttendanceSummary:
    salesman_id: str
    present: int | None = None
    absent: int | None = None
    work_minutes: int | None = None
    stocking_done: int | None = None
    stocking_missed: int | None = None


@dataclass
class ParsedWorkbook:
    salesmen: dict[str, ParsedSalesman]
    pos: dict[str, ParsedPosSummary]
    attendance: dict[str, ParsedAttendanceSummary]
    errors: list[RowError]


# -----------------------------------------------------------------------------
# Normalization helpers
# -----------------------------------------------------------------------------


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
logger = logging.getLogger(__name__)


def normalize_header_text(value: Any) -> str:
    """
    Normalize an Excel header cell to a comparable token:
    - lowercased
    - stripped
    - non-alphanumerics collapsed to single spaces
    """
    if value is None:
        return ""
    text = str(value).strip().lower()
    text = _NON_ALNUM_RE.sub(" ", text).strip()
    return " ".join(text.split())


def slugify_salesman_id(name: str) -> str:
    """
    Deterministic salesman_id based on the salesman name.

    NOTE: This is deliberately simple; if you later add an explicit mapping table,
    you can override this behavior without rewriting the importer.
    """
    cleaned = normalize_header_text(name)
    if not cleaned:
        return ""
    return cleaned.replace(" ", "-")


# -----------------------------------------------------------------------------
# Parsing primitives
# -----------------------------------------------------------------------------


_CURRENCY_RE = re.compile(r"[₹$,]")
_PAREN_NEG_RE = re.compile(r"^\((.*)\)$")


def parse_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        return Decimal(int(value))
    if isinstance(value, int):
        return Decimal(value)
    if isinstance(value, float):
        # Avoid float->Decimal surprises for common values.
        return Decimal(str(value))

    text = str(value).strip()
    if not text:
        return None

    m = _PAREN_NEG_RE.match(text)
    if m:
        text = "-" + m.group(1).strip()

    text = _CURRENCY_RE.sub("", text)
    text = text.replace(" ", "")

    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def parse_int(value: Any) -> int | None:
    dec = parse_decimal(value)
    if dec is None:
        return None
    try:
        return int(dec)
    except (ValueError, OverflowError):
        return None


def parse_work_minutes(value: Any) -> int | None:
    """
    Work hours "HH:MM" -> minutes.

    Handles common Excel cell types:
    - "HH:MM" strings
    - datetime.time
    - datetime.timedelta
    - floats representing fraction of a day (Excel time)
    """
    if value is None:
        return None

    if isinstance(value, timedelta):
        return int(round(value.total_seconds() / 60.0))

    if isinstance(value, time):
        return int(value.hour) * 60 + int(value.minute)

    # Excel sometimes provides day fractions for time cells.
    if isinstance(value, (int, float)) and 0 <= float(value) <= 2:
        minutes = float(value) * 24.0 * 60.0
        return int(round(minutes))

    text = str(value).strip()
    if not text:
        return None

    # Accept "H:MM" or "HH:MM"
    if ":" in text:
        parts = text.split(":")
        if len(parts) >= 2:
            hours = parse_int(parts[0])
            mins = parse_int(parts[1])
            if hours is None or mins is None:
                return None
            return hours * 60 + mins

    # Accept "8.5" hours as a fallback
    dec = parse_decimal(text)
    if dec is None:
        return None
    return int(round(float(dec) * 60.0))


def parse_ratio(value: Any) -> tuple[int | None, int | None]:
    """
    Parse ratios like "10/1" into (done, missed).
    """
    if value is None:
        return (None, None)
    text = str(value).strip()
    if not text:
        return (None, None)

    if "/" not in text:
        done = parse_int(text)
        return (done, None)

    left, right = [p.strip() for p in text.split("/", 1)]
    return (parse_int(left), parse_int(right))


# -----------------------------------------------------------------------------
# Header detection (report-style sheets)
# -----------------------------------------------------------------------------


def _first_n(rows: list[list[Any]], n: int) -> list[list[Any]]:
    return rows[: min(len(rows), n)]

def summarize_header_scan(
    rows: list[list[Any]],
    *,
    scan_rows: int = 10,
    max_cols: int = 10,
) -> str:
    """
    Produce a compact summary of the first few rows for header debugging.
    """
    lines: list[str] = []
    for r_idx, row in enumerate(_first_n(rows, scan_rows)):
        cells = [normalize_header_text(c) for c in row][:max_cols]
        if any(cells):
            lines.append(f"r{r_idx + 1}: {cells}")
    return " | ".join(lines) if lines else "<no data>"

def detect_header_row(
    rows: list[list[Any]],
    *,
    required: dict[str, list[str]],
    optional: dict[str, list[str]] | None = None,
    scan_rows: int = 30,
) -> tuple[int, dict[str, int]]:
    """
    Find the header row by scanning the first `scan_rows` rows and looking for
    required column names.

    Returns:
      (header_row_index, column_index_map)

    Raises:
      ValueError if no suitable header is found.
    """
    optional = optional or {}

    required_norm = {
        k: [normalize_header_text(x) for x in v] for k, v in required.items()
    }
    optional_norm = {k: [normalize_header_text(x) for x in v] for k, v in optional.items()}

    # Expected required keys must all be present to accept a row.
    must_have = set(required_norm.keys())

    def header_matches(cell: str, synonym: str) -> bool:
        """
        Match a sheet header cell to a synonym using conservative heuristics.

        We avoid full fuzzy matching, but allow the common "No. of X" style:
        - exact match
        - synonym token set is a subset of cell tokens (e.g., "customers" matches "no of customers")
        - substring match for compact headers (e.g., "workhours" matches "work hours")
        """
        if not cell or not synonym:
            return False
        if cell == synonym:
            return True

        cell_tokens = set(cell.split())
        syn_tokens = set(synonym.split())
        if syn_tokens and syn_tokens.issubset(cell_tokens):
            return True

        if synonym in cell:
            return True
        return False

    for r_idx, row in enumerate(_first_n(rows, scan_rows)):
        norm_cells = [normalize_header_text(c) for c in row]
        found: dict[str, int] = {}

        # Find required columns.
        for key, synonyms in required_norm.items():
            for c_idx, cell in enumerate(norm_cells):
                if cell and any(header_matches(cell, s) for s in synonyms):
                    found[key] = c_idx
                    break

        if must_have.issubset(found.keys()):
            # Add optional columns if present.
            for key, synonyms in optional_norm.items():
                for c_idx, cell in enumerate(norm_cells):
                    if cell and any(header_matches(cell, s) for s in synonyms):
                        found.setdefault(key, c_idx)
                        break
            return (r_idx, found)

    raise ValueError("Could not detect header row (required columns not found)")


def iter_data_rows(
    sheet_name: str,
    rows: list[list[Any]],
    *,
    header_row_index: int,
    salesman_col_index: int,
) -> Iterable[tuple[int, list[Any]]]:
    """
    Yield (excel_row_number, row_values) for rows after the header.

    Stop conditions:
    - Salesman cell contains "TOTAL" (case-insensitive) or starts with "TOTAL"
    - blank row AFTER we've started reading data
    """
    started = False
    for r_idx in range(header_row_index + 1, len(rows)):
        row = rows[r_idx]
        excel_row_num = r_idx + 1

        # Treat out-of-range as blank.
        salesman_val = row[salesman_col_index] if salesman_col_index < len(row) else None

        # Blank row detection
        if all((c is None or str(c).strip() == "") for c in row):
            if started:
                break
            continue

        started = True

        salesman_text = str(salesman_val).strip() if salesman_val is not None else ""
        if salesman_text and salesman_text.strip().lower().startswith("total"):
            break

        yield (excel_row_num, row)


# -----------------------------------------------------------------------------
# Sheet parsers
# -----------------------------------------------------------------------------


def parse_pos_sheet(sheet_name: str, rows: list[list[Any]]) -> ParsedWorkbook:
    """
    Parse a POS sheet into per-salesman summaries.
    """
    errors: list[RowError] = []
    salesmen: dict[str, ParsedSalesman] = {}
    pos: dict[str, ParsedPosSummary] = {}

    required = {
        "salesman": ["salesman", "sales man", "sales person", "name"],
        "qty": ["qty", "quantity"],
        "net_sales": ["net sales", "netsales", "net sale", "net amount", "amount"],
        "customers": ["customers", "customer"],
    }
    optional = {
        "bills": ["bills", "bill", "invoices", "invoice"],
        "return_customers": ["return customers", "returning customers", "repeat customers"],
        "department": ["department", "dept"],
    }

    try:
        header_idx, cols = detect_header_row(rows, required=required, optional=optional)
    except ValueError as e:
        logger.warning(
            "pos header detection failed: %s | scan=%s",
            e,
            summarize_header_scan(rows),
        )
        return ParsedWorkbook({}, {}, {}, [RowError(sheet_name, 1, str(e))])

    salesman_col = cols["salesman"]

    for excel_row, row in iter_data_rows(
        sheet_name, rows, header_row_index=header_idx, salesman_col_index=salesman_col
    ):
        name_val = row[salesman_col] if salesman_col < len(row) else None
        name = str(name_val).strip() if name_val is not None else ""
        if not name:
            continue

        salesman_id = slugify_salesman_id(name)
        if not salesman_id:
            errors.append(RowError(sheet_name, excel_row, "Invalid salesman name"))
            continue

        dept: str | None = None
        if "department" in cols and cols["department"] < len(row):
            dept_val = row[cols["department"]]
            dept = str(dept_val).strip() if dept_val is not None and str(dept_val).strip() else None

        salesmen.setdefault(salesman_id, ParsedSalesman(salesman_id=salesman_id, name=name, department=dept))

        def col_value(key: str) -> Any:
            idx = cols.get(key)
            if idx is None:
                return None
            return row[idx] if idx < len(row) else None

        def has_value(v: Any) -> bool:
            return v is not None and str(v).strip() != ""

        raw_qty = col_value("qty")
        raw_net_sales = col_value("net_sales")
        raw_customers = col_value("customers")

        qty = parse_decimal(raw_qty)
        net_sales = parse_decimal(raw_net_sales)
        customers = parse_int(raw_customers)

        if has_value(raw_qty) and qty is None:
            errors.append(RowError(sheet_name, excel_row, f"Invalid Qty value: {raw_qty!r}"))
        if has_value(raw_net_sales) and net_sales is None:
            errors.append(
                RowError(sheet_name, excel_row, f"Invalid Net Sales value: {raw_net_sales!r}")
            )
        if has_value(raw_customers) and customers is None:
            errors.append(
                RowError(sheet_name, excel_row, f"Invalid Customers value: {raw_customers!r}")
            )

        bills = parse_int(col_value("bills")) if "bills" in cols else None
        return_customers = (
            parse_int(col_value("return_customers")) if "return_customers" in cols else None
        )

        if qty is None and net_sales is None and customers is None:
            # Likely a separator row; ignore.
            continue

        cur = pos.get(salesman_id) or ParsedPosSummary(salesman_id=salesman_id)

        # Sum fields (report may contain multiple rows per salesman in some stores).
        cur.qty = (cur.qty or Decimal(0)) + (qty or Decimal(0)) if qty is not None else cur.qty
        cur.net_sales = (
            (cur.net_sales or Decimal(0)) + (net_sales or Decimal(0))
            if net_sales is not None
            else cur.net_sales
        )
        cur.customers = (cur.customers or 0) + (customers or 0) if customers is not None else cur.customers

        if bills is not None:
            cur.bills = (cur.bills or 0) + bills
        if return_customers is not None:
            cur.return_customers = (cur.return_customers or 0) + return_customers

        pos[salesman_id] = cur

    return ParsedWorkbook(salesmen=salesmen, pos=pos, attendance={}, errors=errors)


def parse_attendance_sheet(sheet_name: str, rows: list[list[Any]]) -> ParsedWorkbook:
    errors: list[RowError] = []
    salesmen: dict[str, ParsedSalesman] = {}
    attendance: dict[str, ParsedAttendanceSummary] = {}

    required = {
        "salesman": ["salesman", "sales man", "sales person", "name"],
        "present": ["present", "presents", "days present"],
        "absent": ["absent", "absents", "days absent"],
        "work_hours": ["work hours", "workhours", "workhrs", "work hrs", "work hour"],
    }
    optional = {
        "stocking": ["stocking", "stocking ratio", "stocking done/missed", "stocking done missed"],
        "department": ["department", "dept"],
    }

    try:
        header_idx, cols = detect_header_row(rows, required=required, optional=optional)
    except ValueError as e:
        logger.warning(
            "attendance header detection failed: %s | scan=%s",
            e,
            summarize_header_scan(rows),
        )
        return ParsedWorkbook({}, {}, {}, [RowError(sheet_name, 1, str(e))])

    salesman_col = cols["salesman"]

    for excel_row, row in iter_data_rows(
        sheet_name, rows, header_row_index=header_idx, salesman_col_index=salesman_col
    ):
        name_val = row[salesman_col] if salesman_col < len(row) else None
        name = str(name_val).strip() if name_val is not None else ""
        if not name:
            continue

        salesman_id = slugify_salesman_id(name)
        if not salesman_id:
            errors.append(RowError(sheet_name, excel_row, "Invalid salesman name"))
            continue

        dept: str | None = None
        if "department" in cols and cols["department"] < len(row):
            dept_val = row[cols["department"]]
            dept = str(dept_val).strip() if dept_val is not None and str(dept_val).strip() else None

        salesmen.setdefault(salesman_id, ParsedSalesman(salesman_id=salesman_id, name=name, department=dept))

        def col_value(key: str) -> Any:
            idx = cols.get(key)
            if idx is None:
                return None
            return row[idx] if idx < len(row) else None

        def has_value(v: Any) -> bool:
            return v is not None and str(v).strip() != ""

        raw_present = col_value("present")
        raw_absent = col_value("absent")
        raw_work = col_value("work_hours")

        present = parse_int(raw_present)
        absent = parse_int(raw_absent)
        work_minutes = parse_work_minutes(raw_work)

        if has_value(raw_present) and present is None:
            errors.append(RowError(sheet_name, excel_row, f"Invalid Present value: {raw_present!r}"))
        if has_value(raw_absent) and absent is None:
            errors.append(RowError(sheet_name, excel_row, f"Invalid Absent value: {raw_absent!r}"))
        if has_value(raw_work) and work_minutes is None:
            errors.append(
                RowError(sheet_name, excel_row, f"Invalid Work Hours value: {raw_work!r}")
            )

        stocking_done: int | None = None
        stocking_missed: int | None = None
        if "stocking" in cols:
            raw_stocking = col_value("stocking")
            stocking_done, stocking_missed = parse_ratio(raw_stocking)
            if has_value(raw_stocking) and stocking_done is None and stocking_missed is None:
                errors.append(
                    RowError(sheet_name, excel_row, f"Invalid Stocking value: {raw_stocking!r}")
                )

        if present is None and absent is None and work_minutes is None:
            continue

        cur = attendance.get(salesman_id) or ParsedAttendanceSummary(salesman_id=salesman_id)

        if present is not None:
            cur.present = (cur.present or 0) + present
        if absent is not None:
            cur.absent = (cur.absent or 0) + absent
        if work_minutes is not None:
            cur.work_minutes = (cur.work_minutes or 0) + work_minutes
        if stocking_done is not None:
            cur.stocking_done = (cur.stocking_done or 0) + stocking_done
        if stocking_missed is not None:
            cur.stocking_missed = (cur.stocking_missed or 0) + stocking_missed

        attendance[salesman_id] = cur

    return ParsedWorkbook(salesmen=salesmen, pos={}, attendance=attendance, errors=errors)


def merge_parsed(pos: ParsedWorkbook, att: ParsedWorkbook) -> ParsedWorkbook:
    errors = list(pos.errors) + list(att.errors)

    salesmen = dict(pos.salesmen)
    for sid, s in att.salesmen.items():
        # Prefer POS name/department if present; otherwise take attendance.
        salesmen.setdefault(sid, s)

    return ParsedWorkbook(
        salesmen=salesmen,
        pos=pos.pos,
        attendance=att.attendance,
        errors=errors,
    )
