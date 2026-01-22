from __future__ import annotations

from uuid import uuid4

from app.hr.onboarding_storage import build_onboarding_document_paths


def test_build_onboarding_document_paths_is_under_hr_onboarding_base() -> None:
    employee_id = uuid4()
    doc_id = uuid4()
    paths = build_onboarding_document_paths(
        employee_id=employee_id,
        document_id=doc_id,
        original_filename="id.png",
    )

    assert paths.file_rel.startswith(f"hr/onboarding/{employee_id}/{doc_id}/files/")
    assert paths.file_rel.endswith("/id.png")


def test_build_onboarding_document_paths_sanitizes_filename() -> None:
    employee_id = uuid4()
    doc_id = uuid4()
    paths = build_onboarding_document_paths(
        employee_id=employee_id,
        document_id=doc_id,
        original_filename="../../etc/passwd",
    )

    # Directory traversal should be removed.
    assert paths.file_rel.endswith("/passwd")

