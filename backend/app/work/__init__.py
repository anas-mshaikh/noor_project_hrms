"""
Work domain package.

Phase 1 (Auto Task Assignment) lives here:
- deterministic scoring & eligibility rules
- background RQ job for bulk assignment

Database tables are in the `work` and `skills` schemas.
Postgres remains the source of truth; RQ is used only for async execution.
"""

