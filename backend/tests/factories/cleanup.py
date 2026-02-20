"""
Cleanup helpers for tests.

Most API tests commit transactions through the app session, so rollback fixtures
are not sufficient. The recommended approach is:
- seed tenant(s)
- run test actions
- delete the tenant row (cascades)
- delete global users explicitly

The global cleanup registry is implemented in tests/conftest.py.
This module exists as a placeholder for future "bulk cleanup" helpers if the
suite grows significantly.
"""

from __future__ import annotations
