"""
Unit tests for HR profile change change_set normalization/validation.

These tests are intentionally DB-free (pure validation) and should remain fast.
"""

from __future__ import annotations

import pytest

from app.core.errors import AppError
from app.domains.profile_change.change_set import normalize_change_set


pytestmark = [pytest.mark.unit]


def test_normalize_change_set_defaults_primary_bank_account() -> None:
    # ------------------------------------------------------------------
    # Arrange
    # ------------------------------------------------------------------
    raw = {
        "bank_accounts": [
            {"iban": "SA123", "bank_name": "B1"},
            {"account_number": "456", "bank_name": "B2"},
        ]
    }

    # ------------------------------------------------------------------
    # Act
    # ------------------------------------------------------------------
    out = normalize_change_set(raw)

    # ------------------------------------------------------------------
    # Assert
    # ------------------------------------------------------------------
    assert out["bank_accounts"][0]["is_primary"] is True
    assert out["bank_accounts"][1]["is_primary"] is False


def test_normalize_change_set_rejects_unknown_top_level_keys() -> None:
    # ------------------------------------------------------------------
    # Arrange / Act
    # ------------------------------------------------------------------
    with pytest.raises(AppError) as exc:
        normalize_change_set({"unknown_key": 1})

    # ------------------------------------------------------------------
    # Assert
    # ------------------------------------------------------------------
    assert exc.value.code == "hr.profile_change.invalid_change_set"

