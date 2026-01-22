from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from app.core import config as cfg
from app.hr.views import build_resume_views
from app.models.models import HRResume


def test_build_resume_views_headings(monkeypatch, tmp_path: Path) -> None:
    # Point DATA_DIR at a temp folder so we can write artifacts safely.
    monkeypatch.setattr(cfg.settings, "data_dir", str(tmp_path))
    # Lower threshold so short test sections are included.
    monkeypatch.setattr(cfg.settings, "hr_view_min_chars", 1)

    opening_id = uuid4()
    resume_id = uuid4()

    rel_clean = f"hr/resumes/{opening_id}/{resume_id}/parsed/clean.txt"
    abs_clean = tmp_path / rel_clean
    abs_clean.parent.mkdir(parents=True, exist_ok=True)
    abs_clean.write_text(
        "JOHN DOE\n\nSKILLS\nPython, SQL\n\nEXPERIENCE\nCompany A - Engineer\n",
        "utf-8",
    )

    resume = HRResume(
        id=resume_id,
        opening_id=opening_id,
        store_id=uuid4(),
        batch_id=None,
        original_filename="resume.pdf",
        file_path=f"hr/resumes/{opening_id}/{resume_id}/original/resume.pdf",
        status="PARSED",
        clean_text_path=rel_clean,
    )

    views = build_resume_views(resume)
    assert "full" in views
    assert "skills" in views
    assert "experience" in views
    assert "Python" in views["skills"]
    assert "Company A" in views["experience"]


def test_build_resume_views_skills_fallback(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cfg.settings, "data_dir", str(tmp_path))
    monkeypatch.setattr(cfg.settings, "hr_view_min_chars", 1)

    opening_id = uuid4()
    resume_id = uuid4()

    rel_clean = f"hr/resumes/{opening_id}/{resume_id}/parsed/clean.txt"
    abs_clean = tmp_path / rel_clean
    abs_clean.parent.mkdir(parents=True, exist_ok=True)
    abs_clean.write_text(
        "Random text\nPython, SQL, Docker\nMore text\n",
        "utf-8",
    )

    resume = HRResume(
        id=resume_id,
        opening_id=opening_id,
        store_id=uuid4(),
        batch_id=None,
        original_filename="resume.pdf",
        file_path=f"hr/resumes/{opening_id}/{resume_id}/original/resume.pdf",
        status="PARSED",
        clean_text_path=rel_clean,
    )

    views = build_resume_views(resume)
    assert "full" in views
    assert "skills" in views
    assert "Python" in views["skills"]

