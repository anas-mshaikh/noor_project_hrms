from __future__ import annotations

from typing import Any


def sheet_to_matrix(
    ws: Any, *, max_rows: int = 10000, max_cols: int = 80
) -> list[list[object]]:
    """
    Convert an openpyxl worksheet into a simple list-of-lists matrix.

    We keep this in a separate helper so that:
    - parsing logic is unit-testable without openpyxl,
    - the FastAPI route can lazily import openpyxl and then call this.
    """
    max_row = min(int(getattr(ws, "max_row", 0) or 0), max_rows) or max_rows

    out: list[list[object]] = []
    for row in ws.iter_rows(
        min_row=1,
        max_row=max_row,
        max_col=max_cols,
        values_only=True,
    ):
        out.append(list(row))
    return out

