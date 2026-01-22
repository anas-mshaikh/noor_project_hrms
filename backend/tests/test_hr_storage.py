from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from app.hr.storage import build_resume_paths, sanitize_filename, safe_resolve_under_data_dir


def test_sanitize_filename_strips_paths_and_weird_chars() -> None:
    # Directory traversal attempts should be reduced to a safe basename.
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename(r"..\\..\\evil.pdf") == "evil.pdf"

    # Unsafe characters become underscores.
    assert sanitize_filename("John Doe (CV).pdf") == "John_Doe_CV.pdf"


def test_build_resume_paths_are_under_hr_base() -> None:
    opening_id = uuid4()
    resume_id = uuid4()
    paths = build_resume_paths(
        opening_id=opening_id, resume_id=resume_id, original_filename="my.pdf"
    )

    assert paths.raw_rel.startswith(f"hr/resumes/{opening_id}/{resume_id}/original/")
    assert paths.parsed_json_rel.endswith("/parsed/parsed.json")
    assert paths.clean_text_rel.endswith("/parsed/clean.txt")


def test_safe_resolve_under_data_dir_rejects_escape(monkeypatch) -> None:
    # Ensure the helper prevents a DB row from escaping the data_dir boundary.
    # We set data_dir to a known temp path to make this deterministic.
    from app.core import config as cfg

    tmp = Path("/tmp/att_test_data").resolve()
    monkeypatch.setattr(cfg.settings, "data_dir", str(tmp))

    with pytest.raises(ValueError):
        safe_resolve_under_data_dir("../outside.txt")
