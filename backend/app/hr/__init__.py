"""
HR module (Phase 1).

This package implements:
- Hiring "openings" (store-scoped).
- Resume upload to local disk.
- Background parsing via RQ + Unstructured.

Important:
- This is a NEW module and intentionally does not reuse the CCTV "jobs" concept.
- All file paths stored in DB are relative to `settings.data_dir` for portability.
"""

