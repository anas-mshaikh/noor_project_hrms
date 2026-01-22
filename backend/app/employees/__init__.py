"""
employees package

This package intentionally contains *domain-level* employee helpers that are reused across
routers/features (e.g., ATS onboarding -> Employee creation).

Why this exists:
- We want ONE canonical place for employee creation validation/behavior.
- Routers should not duplicate business logic.
"""

