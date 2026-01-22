from __future__ import annotations

from app.hr.pii import redact_pii


def test_redact_pii_replaces_common_patterns() -> None:
    text = (
        "Contact: test@example.com, +1 (415) 555-1234, Aadhaar 1234 5678 9012, "
        "PAN ABCDE1234F, account 12345678"
    )
    out = redact_pii(text)

    assert "[EMAIL]" in out
    assert "[PHONE]" in out
    # Aadhaar + PAN should both be treated as IDs.
    assert out.count("[ID]") >= 2
    # Long digit sequences fallback.
    assert "[NUMBER]" in out

