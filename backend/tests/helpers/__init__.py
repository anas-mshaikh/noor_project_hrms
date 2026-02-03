"""Shared helpers for backend integration tests.

Keep helpers lightweight and avoid importing modules that require DATABASE_URL
at import time. Prefer dynamic imports inside helper functions.
"""

