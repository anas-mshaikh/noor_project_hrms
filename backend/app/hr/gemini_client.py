"""
Gemini API client (Phase 4: Explanations).

We intentionally keep this as a thin, dependency-light wrapper around the
`generateContent` REST API:
  POST https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key=API_KEY

Why a custom client (instead of an SDK)?
- Keeps container size small and dependencies minimal.
- Makes it easy to swap LLM providers later in MVP.

Safety / privacy:
- We send PII-redacted + truncated resume text (see `app.hr.pii`).
- We store only structured JSON in Postgres.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any

import requests

from app.core.config import settings


logger = logging.getLogger(__name__)


class GeminiClientError(RuntimeError):
    """
    Raised for request/response failures when calling Gemini.
    """


_REQUIRED_KEYS = {
    "fit_score",
    "one_line_summary",
    "matched_requirements",
    "missing_requirements",
    "strengths",
    "risks",
    "evidence",
}


def generate_explanation(prompt: str) -> dict[str, Any]:
    """
    Call Gemini and return the parsed structured JSON output.

    Retries:
    - 429 and 5xx responses are retried with exponential backoff (max 3 attempts).
    """
    api_key = (settings.gemini_api_key or "").strip()
    if not api_key:
        raise GeminiClientError("GEMINI_API_KEY is missing/empty")

    model = settings.gemini_model
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={api_key}"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        # Keep outputs deterministic-ish for MVP.
        "generationConfig": {"temperature": 0.2},
    }

    timeout = float(settings.gemini_timeout_sec)
    max_attempts = 3
    backoff = 1.0

    last_err: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            resp = requests.post(url, json=payload, timeout=timeout)

            # Retryable failures: rate limits and transient server errors.
            if resp.status_code in {429, 500, 502, 503, 504}:
                raise GeminiClientError(
                    f"gemini_http_{resp.status_code}: {resp.text[:300]}"
                )

            if resp.status_code >= 400:
                raise GeminiClientError(
                    f"gemini_http_{resp.status_code}: {resp.text[:300]}"
                )

            data = resp.json()
            text = _extract_text(data)
            obj = _extract_json_object(text)
            _validate_explanation_json(obj)
            return obj

        except Exception as e:  # noqa: BLE001 - we rewrap with context below
            last_err = e
            if attempt >= max_attempts:
                break

            logger.warning(
                "gemini request failed; retrying",
                extra={
                    "attempt": attempt,
                    "max_attempts": max_attempts,
                    "error": str(e),
                },
            )
            time.sleep(backoff)
            backoff *= 2.0

    raise GeminiClientError(f"gemini request failed after retries: {last_err}")


def _extract_text(resp_json: dict[str, Any]) -> str:
    """
    Extract the model text output from a Gemini `generateContent` response.

    We keep this defensive because response shapes can vary slightly.
    """
    candidates = resp_json.get("candidates") or []
    if not candidates:
        raise GeminiClientError("Gemini response has no candidates")

    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    texts: list[str] = []
    for p in parts:
        t = p.get("text")
        if t:
            texts.append(str(t))

    if not texts:
        raise GeminiClientError("Gemini response has no text parts")
    return "\n".join(texts).strip()


def _extract_json_object(text: str) -> dict[str, Any]:
    """
    Best-effort extraction of a JSON object from model output.

    Even when we instruct "JSON only", models may return:
    - code fences (```json ... ```)
    - extra whitespace

    We extract the first {...} block and parse it as JSON.
    """
    raw = (text or "").strip()

    # Strip common code-fence wrappers.
    if raw.startswith("```"):
        raw = raw.strip("`")
        # Some models add a leading "json" label.
        raw = raw.lstrip().removeprefix("json").lstrip()

    # Fast path: already valid JSON.
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise GeminiClientError("Could not find JSON object in Gemini output")

    snippet = raw[start : end + 1]
    try:
        parsed = json.loads(snippet)
    except Exception as e:
        raise GeminiClientError(f"Invalid JSON from Gemini: {e}") from e

    if not isinstance(parsed, dict):
        raise GeminiClientError("Gemini output JSON is not an object")

    return parsed


def _validate_explanation_json(obj: dict[str, Any]) -> None:
    """
    Minimal schema validation for the explanation output.

    We keep this intentionally lightweight:
    - ensure required keys exist,
    - ensure evidence is a list of {claim, quote},
    - coerce fit_score when possible.
    """
    missing = _REQUIRED_KEYS.difference(obj.keys())
    if missing:
        raise GeminiClientError(f"Gemini JSON missing keys: {sorted(missing)}")

    # Fit score: allow strings/numbers but normalize to int in [0..100].
    fit = obj.get("fit_score")
    try:
        fit_n = float(fit)
    except Exception as e:
        raise GeminiClientError(f"Invalid fit_score: {fit}") from e

    # Clamp for safety.
    fit_n = max(0.0, min(100.0, fit_n))
    obj["fit_score"] = fit_n

    evidence = obj.get("evidence") or []
    if not isinstance(evidence, list):
        raise GeminiClientError("evidence must be a list")

    for item in evidence:
        if not isinstance(item, dict):
            raise GeminiClientError("evidence items must be objects")
        if "claim" not in item or "quote" not in item:
            raise GeminiClientError("evidence items must include claim and quote")

