from __future__ import annotations

from app.hr.onboarding_defaults import DEFAULT_ONBOARDING_TASKS


def test_default_onboarding_tasks_have_doc_type_metadata_for_document_tasks() -> None:
    """
    Ensure DOCUMENT tasks include a doc_type in metadata_json.

    This allows the upload endpoint to auto-complete the correct checklist item.
    """

    doc_tasks = [t for t in DEFAULT_ONBOARDING_TASKS if t.task_type == "DOCUMENT"]
    assert doc_tasks, "expected at least one DOCUMENT task in default checklist"

    for t in doc_tasks:
        assert "doc_type" in t.metadata_json
        assert isinstance(t.metadata_json["doc_type"], str)
        assert t.metadata_json["doc_type"].strip()

