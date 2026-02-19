"""
Profile change domain public service exports (Milestone 6).

Historically this domain started with a single large `service.py`. As the module
grew (API operations + workflow terminal apply logic + change-set validation),
it was split into smaller files to keep each module readable and testable.

This file intentionally re-exports the public entrypoints so existing imports
remain stable:
- `ProfileChangeService` (API-facing operations)
- `ProfileChangeApplyService` (workflow terminal hook side-effects)
- `normalize_change_set` (shared validator used by onboarding packet submission)
"""

from __future__ import annotations

from app.domains.profile_change.change_set import normalize_change_set
from app.domains.profile_change.service_api import ProfileChangeService
from app.domains.profile_change.service_apply import ProfileChangeApplyService


__all__ = [
    "ProfileChangeApplyService",
    "ProfileChangeService",
    "normalize_change_set",
]
