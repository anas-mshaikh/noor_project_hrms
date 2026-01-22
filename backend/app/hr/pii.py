"""
PII redaction and candidate context building for HR explanations (Phase 4).

We send resume text to an external LLM API (Gemini) to generate explanations. Even
though this is a dev product, we should avoid sending obvious PII whenever possible.

This module provides:
- `redact_pii(text)`: MVP regex-based redaction.
- `build_candidate_context(resume)`: redacted, truncated context for prompting.

Limitations:
- Regex redaction is imperfect and may miss some PII or over-redact some numeric data.
- This is acceptable for MVP; we can improve later with a dedicated PII detector.
"""

from __future__ import annotations

import re

from app.core.config import settings
from app.hr.views import build_resume_views, truncate_text
from app.models.models import HRResume


_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

# Aadhaar-like: 12 digits grouped (India), e.g. 1234 5678 9012
_AADHAAR_RE = re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")

# PAN-like: 5 letters + 4 digits + 1 letter (India), e.g. ABCDE1234F
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")

# Candidate phone-like tokens. We post-filter by digit count to reduce false positives.
_PHONE_CANDIDATE_RE = re.compile(r"\+?\d[\d\s().-]{7,}\d")

# Long digit sequences (account numbers, IDs, etc.). We keep this conservative.
_LONG_DIGITS_RE = re.compile(r"\b\d{8,}\b")


def redact_pii(text: str) -> str:
    """
    Redact common PII patterns.

    MVP behavior:
    - emails -> [EMAIL]
    - phone numbers -> [PHONE]
    - PAN/Aadhaar-like IDs -> [ID]
    - other long digit sequences -> [NUMBER]
    """
    t = text or ""

    # Emails
    t = _EMAIL_RE.sub("[EMAIL]", t)

    # National IDs (examples: Aadhaar/PAN)
    t = _AADHAAR_RE.sub("[ID]", t)
    t = _PAN_RE.sub("[ID]", t)

    # Phone numbers (heuristic).
    # We replace only if the matched token contains 10–15 digits (common range).
    def _phone_repl(match: re.Match[str]) -> str:
        token = match.group(0)
        digits = re.sub(r"\D", "", token)
        if 10 <= len(digits) <= 15:
            return "[PHONE]"
        return token

    t = _PHONE_CANDIDATE_RE.sub(_phone_repl, t)

    # Long digit sequences (fallback).
    t = _LONG_DIGITS_RE.sub("[NUMBER]", t)

    return t


def build_candidate_context(resume: HRResume) -> str:
    """
    Build a compact redacted context block for prompting.

    - Prefer "skills"+"experience" when available (more signal, less noise).
    - Fallback to "full".
    - Redact PII using `redact_pii`.
    - Truncate to a safe maximum size (char-based) to control latency/cost.
    """
    views = build_resume_views(resume)

    compact = (views.get("skills", "") + "\n" + views.get("experience", "")).strip()
    if not compact:
        compact = views.get("full", "")

    compact = redact_pii(compact)

    # NOTE: We reuse HR_RERANKER_MAX_CHARS as the shared "safe max chars" knob.
    # This avoids introducing too many separate tuning parameters for MVP.
    compact = truncate_text(compact, max_chars=int(settings.hr_reranker_max_chars))

    # Context header: only stable identifiers (avoid names/emails here).
    header = (
        f"resume_id: {resume.id}\n"
        f"original_filename: {resume.original_filename}\n"
    )

    return (header + "\n" + compact).strip()

