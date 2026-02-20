"""
Test data factories (enterprise testing infra).

Factories create domain objects for tests in a deterministic way.

Rules:
- Prefer explicit factory functions over magic.
- Keep outputs small (ids + minimal metadata).
- Do not hide important setup steps (workflow definitions, role assignments).
"""

from __future__ import annotations
