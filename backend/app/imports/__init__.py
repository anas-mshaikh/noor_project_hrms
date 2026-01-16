"""
Phase 2 imports package.

This package is intentionally "pure python" and testable:
- Parsing utilities operate on a 2D matrix of values (list[list[object]]).
- The FastAPI endpoint is responsible for reading the Excel workbook (openpyxl)
  and converting each sheet into that matrix.
"""

