"""
Resume "views" builder (Phase 2).

We build 2–3 derived texts per resume:
- full: the full clean resume text (always produced)
- skills: best-effort extracted skills section
- experience: best-effort extracted work experience section

Why multiple views?
- They allow targeted retrieval later (skills search, experience relevance) without
  needing rerankers or complex pipelines in the MVP.

This module is deliberately heuristic and conservative:
- If we can't find a section reliably, we return an empty string for that view.
- We only keep non-empty views above `settings.hr_view_min_chars`.
"""

from __future__ import annotations

import hashlib
import json
import re

from app.core.config import settings
from app.hr.storage import safe_resolve_under_data_dir
from app.models.models import HRResume


_HEADING_SKILLS = {
    "SKILLS",
    "TECHNICAL SKILLS",
    "CORE SKILLS",
    "TOOLS",
    "TECHNOLOGIES",
    "TECH STACK",
}

_HEADING_EXPERIENCE = {
    "EXPERIENCE",
    "WORK EXPERIENCE",
    "PROFESSIONAL EXPERIENCE",
    "EMPLOYMENT",
    "EMPLOYMENT HISTORY",
}

# Used to detect section headings in semi-structured resume text.
_HEADING_LINE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9 /&()+._-]{2,60}:?$")


def normalize_text(text: str) -> str:
    """
    Normalize text for hashing and embedding.

    We keep this intentionally simple (and deterministic):
- normalize newlines
- strip trailing spaces per line
- collapse excessive blank lines
    """
    t = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [ln.rstrip() for ln in t.split("\n")]

    # Collapse consecutive blank lines to at most 2 (keeps readability).
    out_lines: list[str] = []
    blank_run = 0
    for ln in lines:
        if ln.strip() == "":
            blank_run += 1
            if blank_run <= 2:
                out_lines.append("")
        else:
            blank_run = 0
            out_lines.append(ln)

    return "\n".join(out_lines).strip()


def truncate_text(text: str, *, max_chars: int) -> str:
    """
    Cheap safety truncation (character-based).

    BGE-M3 can handle long context, but extremely large inputs can still blow up
    memory/latency. We keep this configurable via env.
    """
    if max_chars <= 0:
        return text
    return text[:max_chars]


def text_hash(text: str) -> str:
    """
    Hash the exact text used for embedding.

    This enables idempotency: if the text hasn't changed, we can skip re-embedding.
    """
    h = hashlib.sha256()
    h.update(text.encode("utf-8", errors="replace"))
    return h.hexdigest()


def _load_resume_clean_text(resume: HRResume) -> str:
    """
    Load the resume clean text from disk.

    Priority:
    1) clean_text_path (plain text file written by parse_resume)
    2) parsed.json["clean_text"]
    """
    if resume.clean_text_path:
        p = safe_resolve_under_data_dir(resume.clean_text_path)
        if p.exists():
            return p.read_text("utf-8", errors="replace")

    if resume.parsed_path:
        p = safe_resolve_under_data_dir(resume.parsed_path)
        if p.exists():
            raw = p.read_text("utf-8", errors="replace")
            try:
                payload = json.loads(raw)
                return str(payload.get("clean_text") or "")
            except Exception:
                return ""

    return ""


def _extract_section_by_heading(text: str, headings: set[str]) -> str:
    """
    Extract a section by heading names (best-effort).

    Heuristic:
    - Find the first line that looks like a heading and matches one of `headings`
    - Capture lines until the next heading-like line (or end)
    """
    lines = text.split("\n")

    heading_idx: int | None = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        # Normalize heading name (ignore trailing colon)
        key = s.rstrip(":").upper()
        if key in headings:
            heading_idx = i
            break

    if heading_idx is None:
        return ""

    # Capture until next heading-like line.
    buf: list[str] = []
    for ln in lines[heading_idx + 1 :]:
        s = ln.strip()
        if s and _HEADING_LINE_RE.match(s) and s.rstrip(":").upper() not in headings:
            break
        buf.append(ln)

    return "\n".join(buf).strip()


def _skills_fallback(text: str) -> str:
    """
    Very lightweight fallback for skills:
    - collect early lines that look like bullet lists or comma-separated skill lines
    """
    lines = [ln.strip() for ln in text.split("\n")]
    candidates: list[str] = []
    for ln in lines[:200]:
        if not ln:
            continue
        if ln.startswith(("•", "-", "*")):
            candidates.append(ln.lstrip("•-* ").strip())
            continue
        if "," in ln and len(ln) <= 140:
            candidates.append(ln)

        if len(candidates) >= 40:
            break

    return "\n".join(candidates).strip()


def build_resume_views(resume: HRResume) -> dict[str, str]:
    """
    Build resume views to embed.

    Returns a dict with:
      {"full": "...", "skills": "...", "experience": "..."}  (skills/experience optional)
    """
    raw = _load_resume_clean_text(resume)
    full = truncate_text(
        normalize_text(raw),
        max_chars=int(settings.hr_embed_max_chars),
    )

    # `full` is required even if it's empty (embedding task will fail clearly).
    views: dict[str, str] = {"full": full}

    # Derived views (only keep if meaningful).
    skills = _extract_section_by_heading(full, _HEADING_SKILLS) or _skills_fallback(full)
    skills = normalize_text(skills)
    if len(skills) >= int(settings.hr_view_min_chars):
        views["skills"] = skills

    exp = _extract_section_by_heading(full, _HEADING_EXPERIENCE)
    exp = normalize_text(exp)
    if len(exp) >= int(settings.hr_view_min_chars):
        views["experience"] = exp

    return views
