from __future__ import annotations

import pytest

from app.hr.gemini_client import _extract_json_object, _validate_explanation_json


def test_extract_json_object_plain() -> None:
    obj = _extract_json_object('{"fit_score": 80, "one_line_summary": "ok", "matched_requirements": [], "missing_requirements": [], "strengths": [], "risks": [], "evidence": []}')
    assert obj["fit_score"] == 80


def test_extract_json_object_code_fence() -> None:
    text = """```json
{
  "fit_score": 50,
  "one_line_summary": "x",
  "matched_requirements": [],
  "missing_requirements": [],
  "strengths": [],
  "risks": [],
  "evidence": []
}
```"""
    obj = _extract_json_object(text)
    assert obj["fit_score"] == 50


def test_validate_explanation_json_requires_keys() -> None:
    with pytest.raises(Exception):
        _validate_explanation_json({"fit_score": 10})


def test_validate_explanation_json_clamps_fit_score() -> None:
    obj = {
        "fit_score": 999,
        "one_line_summary": "x",
        "matched_requirements": [],
        "missing_requirements": [],
        "strengths": [],
        "risks": [],
        "evidence": [{"claim": "c", "quote": "q"}],
    }
    _validate_explanation_json(obj)
    assert obj["fit_score"] == 100.0

