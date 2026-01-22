from __future__ import annotations

from app.hr.ats import DEFAULT_PIPELINE_STAGES, normalize_stage_name


def test_default_pipeline_stages_are_deterministic() -> None:
    """
    Phase 5 ATS relies on a predictable default pipeline for new openings.

    We keep this as a pure-unit test so it runs without a database.
    """

    assert len(DEFAULT_PIPELINE_STAGES) >= 4  # MVP requires at least a few stages

    names = [s.name for s in DEFAULT_PIPELINE_STAGES]
    assert len(names) == len(set(names)), "stage names must be unique"

    sort_orders = [s.sort_order for s in DEFAULT_PIPELINE_STAGES]
    assert sort_orders == sorted(sort_orders), "sort_order must be monotonic"

    terminal = {s.name for s in DEFAULT_PIPELINE_STAGES if s.is_terminal}
    # We expect at least one terminal state for a usable ATS.
    assert terminal, "must have terminal stages"
    # MVP defaults include both outcomes.
    assert "Hired" in terminal
    assert "Rejected" in terminal


def test_normalize_stage_name_is_casefolded_and_whitespace_collapsed() -> None:
    assert normalize_stage_name("  Screened  ") == "screened"
    assert normalize_stage_name("Work   In   Progress") == "work in progress"
    assert normalize_stage_name("") == ""

