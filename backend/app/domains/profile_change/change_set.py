"""
Profile change request change-set validation (Milestone 6).

This module defines the v1 "change_set" contract and provides a single
normalization/validation entrypoint: `normalize_change_set`.

Why separate this from services?
- Keeps business validation logic reusable (direct profile change vs onboarding
  "submit packet").
- Keeps API and workflow hook services smaller and focused on persistence.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from app.core.errors import AppError


TOP_LEVEL_KEYS_ORDER: tuple[str, ...] = (
    "phone",
    "address",
    "bank_accounts",
    "government_ids",
    "dependents",
)


def _norm_optional_str(value: Any, *, field: str, max_len: int) -> str | None:
    """Normalize an optional string (trim, enforce max length)."""

    if value is None:
        return None
    if not isinstance(value, str):
        raise AppError(
            code="hr.profile_change.invalid_change_set",
            message=f"{field} must be a string",
            status_code=400,
        )
    v = value.strip()
    if v == "":
        return None
    if len(v) > max_len:
        raise AppError(
            code="hr.profile_change.invalid_change_set",
            message=f"{field} exceeds max length {max_len}",
            status_code=400,
        )
    return v


def _norm_iso_date(value: Any, *, field: str) -> str | None:
    """Normalize an ISO date field (accept date or YYYY-MM-DD string)."""

    if value is None:
        return None
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, str):
        try:
            # Validate format; store canonical ISO string.
            return date.fromisoformat(value).isoformat()
        except Exception as e:  # noqa: BLE001 - stable AppError for clients
            raise AppError(
                code="hr.profile_change.invalid_change_set",
                message=f"{field} must be YYYY-MM-DD",
                status_code=400,
            ) from e
    raise AppError(
        code="hr.profile_change.invalid_change_set",
        message=f"{field} must be a date",
        status_code=400,
    )


def _normalize_bank_accounts(value: Any) -> list[dict[str, Any]]:
    """Validate and normalize bank_accounts list."""

    if not isinstance(value, list):
        raise AppError(
            code="hr.profile_change.invalid_change_set",
            message="bank_accounts must be a list",
            status_code=400,
        )

    out: list[dict[str, Any]] = []
    primary_indexes: list[int] = []

    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            raise AppError(
                code="hr.profile_change.invalid_change_set",
                message="bank_accounts items must be objects",
                status_code=400,
            )

        allowed = {"iban", "account_number", "bank_name", "is_primary"}
        unknown = sorted(set(item.keys()) - allowed)
        if unknown:
            raise AppError(
                code="hr.profile_change.invalid_change_set",
                message="bank_accounts has unknown keys",
                details={"unknown_keys": unknown},
                status_code=400,
            )

        iban = _norm_optional_str(
            item.get("iban"), field="bank_accounts.iban", max_len=64
        )
        account_number = _norm_optional_str(
            item.get("account_number"),
            field="bank_accounts.account_number",
            max_len=64,
        )
        bank_name = _norm_optional_str(
            item.get("bank_name"),
            field="bank_accounts.bank_name",
            max_len=200,
        )
        is_primary = item.get("is_primary")
        if is_primary is None:
            is_primary_bool = False
        elif isinstance(is_primary, bool):
            is_primary_bool = bool(is_primary)
        else:
            raise AppError(
                code="hr.profile_change.invalid_change_set",
                message="bank_accounts.is_primary must be boolean",
                status_code=400,
            )

        if iban is None and account_number is None:
            raise AppError(
                code="hr.profile_change.invalid_change_set",
                message="Each bank account must have iban or account_number",
                status_code=400,
            )

        if is_primary_bool:
            primary_indexes.append(idx)

        out.append(
            {
                "iban": iban,
                "account_number": account_number,
                "bank_name": bank_name,
                "is_primary": is_primary_bool,
            }
        )

    # Enforce a single primary account (deterministic default: first item).
    if len(primary_indexes) > 1:
        raise AppError(
            code="hr.profile_change.invalid_change_set",
            message="Only one bank account can be primary",
            status_code=400,
        )
    if out and not primary_indexes:
        out[0]["is_primary"] = True

    return out


def _normalize_government_ids(value: Any) -> list[dict[str, Any]]:
    """Validate and normalize government_ids list."""

    if not isinstance(value, list):
        raise AppError(
            code="hr.profile_change.invalid_change_set",
            message="government_ids must be a list",
            status_code=400,
        )

    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise AppError(
                code="hr.profile_change.invalid_change_set",
                message="government_ids items must be objects",
                status_code=400,
            )

        allowed = {
            "id_type",
            "id_number",
            "issued_at",
            "expires_at",
            "issuing_country",
            "notes",
        }
        unknown = sorted(set(item.keys()) - allowed)
        if unknown:
            raise AppError(
                code="hr.profile_change.invalid_change_set",
                message="government_ids has unknown keys",
                details={"unknown_keys": unknown},
                status_code=400,
            )

        id_type = _norm_optional_str(
            item.get("id_type"), field="government_ids.id_type", max_len=64
        )
        id_number = _norm_optional_str(
            item.get("id_number"),
            field="government_ids.id_number",
            max_len=128,
        )
        if id_type is None or id_number is None:
            raise AppError(
                code="hr.profile_change.invalid_change_set",
                message="government_ids.id_type and id_number are required",
                status_code=400,
            )

        issued_at = _norm_iso_date(
            item.get("issued_at"), field="government_ids.issued_at"
        )
        expires_at = _norm_iso_date(
            item.get("expires_at"), field="government_ids.expires_at"
        )

        issuing_country = _norm_optional_str(
            item.get("issuing_country"),
            field="government_ids.issuing_country",
            max_len=64,
        )
        notes = _norm_optional_str(
            item.get("notes"), field="government_ids.notes", max_len=10_000
        )

        out.append(
            {
                "id_type": id_type,
                "id_number": id_number,
                "issued_at": issued_at,
                "expires_at": expires_at,
                "issuing_country": issuing_country,
                "notes": notes,
            }
        )

    return out


def _normalize_dependents(value: Any) -> list[dict[str, Any]]:
    """Validate and normalize dependents list."""

    if not isinstance(value, list):
        raise AppError(
            code="hr.profile_change.invalid_change_set",
            message="dependents must be a list",
            status_code=400,
        )

    out: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            raise AppError(
                code="hr.profile_change.invalid_change_set",
                message="dependents items must be objects",
                status_code=400,
            )

        allowed = {"name", "relationship", "dob"}
        unknown = sorted(set(item.keys()) - allowed)
        if unknown:
            raise AppError(
                code="hr.profile_change.invalid_change_set",
                message="dependents has unknown keys",
                details={"unknown_keys": unknown},
                status_code=400,
            )

        name = _norm_optional_str(
            item.get("name"), field="dependents.name", max_len=200
        )
        if name is None:
            raise AppError(
                code="hr.profile_change.invalid_change_set",
                message="dependents.name is required",
                status_code=400,
            )

        relationship = _norm_optional_str(
            item.get("relationship"),
            field="dependents.relationship",
            max_len=64,
        )
        dob = _norm_iso_date(item.get("dob"), field="dependents.dob")

        out.append({"name": name, "relationship": relationship, "dob": dob})

    return out


def normalize_change_set(raw: Any) -> dict[str, Any]:
    """
    Normalize and validate a user-supplied change_set.

    This function is intentionally strict:
    - unknown top-level keys are rejected
    - values must have the expected shape (strings/lists/objects)
    - at least one supported key must be present

    Customization placeholder:
    - Add new supported top-level keys here as Milestone 6 expands.
    """

    if not isinstance(raw, dict):
        raise AppError(
            code="hr.profile_change.invalid_change_set",
            message="change_set must be an object",
            status_code=400,
        )

    allowed = set(TOP_LEVEL_KEYS_ORDER)
    unknown = sorted(set(raw.keys()) - allowed)
    if unknown:
        raise AppError(
            code="hr.profile_change.invalid_change_set",
            message="change_set contains unknown keys",
            details={"unknown_keys": unknown},
            status_code=400,
        )

    out: dict[str, Any] = {}

    if "phone" in raw:
        out["phone"] = _norm_optional_str(raw.get("phone"), field="phone", max_len=32)

    if "address" in raw:
        addr = raw.get("address")
        if addr is None:
            # v1 decision: explicit null means "clear address" -> {}.
            out["address"] = {}
        elif isinstance(addr, dict):
            out["address"] = addr
        else:
            raise AppError(
                code="hr.profile_change.invalid_change_set",
                message="address must be an object",
                status_code=400,
            )

    if "bank_accounts" in raw:
        out["bank_accounts"] = _normalize_bank_accounts(raw.get("bank_accounts"))

    if "government_ids" in raw:
        out["government_ids"] = _normalize_government_ids(raw.get("government_ids"))

    if "dependents" in raw:
        out["dependents"] = _normalize_dependents(raw.get("dependents"))

    if not out:
        raise AppError(
            code="hr.profile_change.invalid_change_set",
            message="change_set must include at least one supported field",
            status_code=400,
        )

    return out
