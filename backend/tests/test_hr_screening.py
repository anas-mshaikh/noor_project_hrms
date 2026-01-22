from __future__ import annotations

from uuid import uuid4

from app.core import config as cfg
from app.hr.tasks import _ScreeningCandidate, _normalized_screening_config


def test_normalized_screening_config_defaults(monkeypatch) -> None:
    """
    When config_json is empty/missing fields, we must use Settings defaults.

    This keeps the screening worker deterministic and avoids hard-coded values inside
    the algorithm (all defaults are env-driven).
    """
    monkeypatch.setattr(
        cfg.settings, "hr_screening_default_view_types", ["skills", "experience", "full"]
    )
    monkeypatch.setattr(cfg.settings, "hr_screening_default_k_per_view", 200)
    monkeypatch.setattr(cfg.settings, "hr_screening_default_pool_size", 400)
    monkeypatch.setattr(cfg.settings, "hr_screening_default_top_n", 200)

    out = _normalized_screening_config({})
    assert out["view_types"] == ["skills", "experience", "full"]
    assert out["k_per_view"] == 200
    assert out["pool_size"] == 400
    assert out["top_n"] == 200


def test_normalized_screening_config_sanitizes_and_clamps(monkeypatch) -> None:
    """
    Config normalization must be robust to messy input (API user errors).

    - view_types: lowercased, deduped, invalid removed; if empty -> default
    - numeric fields: parsed as int where possible and clamped to safe bounds
    - pool_size must be >= top_n
    """
    monkeypatch.setattr(cfg.settings, "hr_screening_default_view_types", ["full"])
    monkeypatch.setattr(cfg.settings, "hr_screening_default_k_per_view", 7)
    monkeypatch.setattr(cfg.settings, "hr_screening_default_pool_size", 9)
    monkeypatch.setattr(cfg.settings, "hr_screening_default_top_n", 3)

    out = _normalized_screening_config(
        {
            "view_types": ["Skills", "invalid", "FULL", "skills"],
            "k_per_view": "not-an-int",
            "pool_size": 0,
            "top_n": 10_000_000,  # intentionally huge: should clamp
        }
    )

    assert out["view_types"] == ["skills", "full"]
    assert out["k_per_view"] == 7
    # top_n gets clamped to an internal max (5000 today); pool_size should follow.
    assert out["top_n"] <= 5000
    assert out["pool_size"] >= out["top_n"]


def test_screening_candidate_sorting_prefers_rerank_then_retrieval() -> None:
    """
    ScreeningRun Phase 3 final ordering is rerank-first (highest impact),
    with retrieval_score used only as a secondary tie-breaker.
    """
    a = _ScreeningCandidate(resume_id=uuid4(), best_view_type="full", retrieval_score=0.99)
    b = _ScreeningCandidate(resume_id=uuid4(), best_view_type="skills", retrieval_score=0.10)
    c = _ScreeningCandidate(resume_id=uuid4(), best_view_type="experience", retrieval_score=0.90)

    # Reranker says B is best overall even though its retrieval score is low.
    a.rerank_score = 0.10
    b.rerank_score = 0.95
    c.rerank_score = 0.50

    pool = [a, b, c]
    pool.sort(key=lambda x: (-x.final_score, -x.retrieval_score, str(x.resume_id)))

    assert pool[0] is b
