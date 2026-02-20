"""
Shared test support utilities.

This package contains small helpers that make tests more consistent and easier
to read:
- app factory wrappers
- API client wrappers (envelope unwrapping)
- assertion helpers
- marker utilities

These modules should contain *test-only* logic and must never be imported by
production code.
"""

from __future__ import annotations

