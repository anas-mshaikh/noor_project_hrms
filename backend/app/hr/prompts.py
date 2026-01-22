"""
Prompt templates for HR (Phase 4: Explanations).

We keep prompts versioned and deterministic so:
- outputs can be audited/reproduced (at least at prompt-level),
- future prompt improvements don't silently change historical explanations.

IMPORTANT PRIVACY NOTE
----------------------
We NEVER store raw resume text in Postgres. We only store the structured JSON output
from the LLM. The prompt/candidate context is built at runtime from local artifacts
and is PII-redacted before being sent to Gemini.
"""

from __future__ import annotations


PROMPT_VERSION = "v1"


def build_explanation_prompt(
    *,
    opening_title: str,
    jd_text: str,
    candidate_context: str,
    language: str = "en",
) -> str:
    """
    Build the LLM prompt for a single candidate explanation.

    Output contract: STRICT JSON only (no Markdown / no prose).

    We keep this prompt conservative:
    - "Use only provided text" to prevent hallucinations.
    - Evidence quotes must be substrings of the candidate context.

    `language` is included as a future-friendly parameter (Phase 4 is English-first).
    """
    # NOTE: We intentionally keep the schema stable and compact for mobile/UI usage.
    # If you change this schema later, bump PROMPT_VERSION.
    schema = """{
  "fit_score": number,                 // 0..100
  "one_line_summary": string,
  "matched_requirements": string[],
  "missing_requirements": string[],
  "strengths": string[],
  "risks": string[],
  "evidence": [
    { "claim": string, "quote": string }
  ]
}"""

    return f"""
You are an expert recruiter assisting with resume screening for a retail/company role.

Task:
- Compare the candidate to the job description.
- Output STRICT JSON ONLY (no markdown, no backticks, no additional text).
- Use ONLY the provided job description and candidate text. Do not guess.
- Keep arrays short (max 6 items each). Keep evidence list max 6 items.
- Every evidence.quote MUST be a short exact substring from the candidate text.
- If information is missing, say so explicitly (e.g., include the requirement under missing_requirements).

Output language: {language}

Required JSON schema (follow exactly):
{schema}

Job opening title:
{opening_title.strip()}

Job description:
{jd_text.strip()}

Candidate text (PII redacted):
{candidate_context.strip()}
""".strip()

