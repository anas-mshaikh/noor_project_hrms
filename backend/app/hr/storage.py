"""
Local storage utilities for the HR module.

Design goals:
- Keep everything under `settings.data_dir` so Docker volume mounts work.
- Store *relative* paths in Postgres, mirroring how videos/events snapshots are stored.
- Prevent path traversal by sanitizing filenames and controlling folder layout.
- Write files atomically using a temporary ".part" file + rename.

Directory layout (all relative to settings.data_dir):
  hr/resumes/{opening_id}/{resume_id}/original/{filename}
  hr/resumes/{opening_id}/{resume_id}/parsed/parsed.json
  hr/resumes/{opening_id}/{resume_id}/parsed/clean.txt
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from app.core.config import settings


_FILENAME_SAFE_RE = re.compile(r"[^A-Za-z0-9._-]+")


def sanitize_filename(filename: str, *, default: str = "resume") -> str:
    """
    Return a filesystem-safe basename.

    Security:
    - strips any directory parts
    - replaces unsafe chars
    - clamps length
    """
    name = Path(filename or "").name.strip()
    if not name:
        name = default

    # Replace unsafe characters so we can safely use this in a folder path.
    name = _FILENAME_SAFE_RE.sub("_", name)

    # Avoid weird edge-cases like "." or ".."
    name = name.strip("._")
    if not name:
        name = default

    # Keep extensions if present, but clamp to keep paths manageable.
    if len(name) > 120:
        stem = Path(name).stem[:100]
        suffix = Path(name).suffix[:20]
        name = f"{stem}{suffix}"

    return name


@dataclass(frozen=True)
class ResumePaths:
    """
    Computed file paths for one resume (relative + absolute).
    """

    raw_rel: str
    parsed_json_rel: str
    clean_text_rel: str

    @property
    def raw_abs(self) -> Path:
        return (Path(settings.data_dir) / self.raw_rel).resolve()

    @property
    def parsed_json_abs(self) -> Path:
        return (Path(settings.data_dir) / self.parsed_json_rel).resolve()

    @property
    def clean_text_abs(self) -> Path:
        return (Path(settings.data_dir) / self.clean_text_rel).resolve()


def build_resume_paths(
    *, opening_id: UUID, resume_id: UUID, original_filename: str
) -> ResumePaths:
    """
    Compute the canonical on-disk paths for a resume.
    """
    safe_name = sanitize_filename(original_filename, default="resume")
    base = f"hr/resumes/{opening_id}/{resume_id}"
    return ResumePaths(
        raw_rel=f"{base}/original/{safe_name}",
        parsed_json_rel=f"{base}/parsed/parsed.json",
        clean_text_rel=f"{base}/parsed/clean.txt",
    )


def _atomic_write_bytes(dest: Path, data: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(dest)


def save_upload_to_disk(upload_file, dest_abs: Path) -> int:
    """
    Stream an UploadFile-like object to disk.

    Returns the number of bytes written.
    """
    dest_abs.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest_abs.with_suffix(dest_abs.suffix + ".part")
    size = 0
    try:
        with tmp.open("wb") as out:
            while True:
                chunk = upload_file.file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                size += len(chunk)
        tmp.replace(dest_abs)
        return size
    finally:
        # UploadFile implements .close() and also holds an underlying file handle.
        try:
            upload_file.file.close()
        except Exception:
            pass


def write_text(dest_abs: Path, text: str) -> None:
    """
    Write UTF-8 text atomically.
    """
    _atomic_write_bytes(dest_abs, text.encode("utf-8", errors="replace"))


def write_json(dest_abs: Path, payload: dict[str, Any]) -> None:
    """
    Write JSON (UTF-8) atomically.
    """
    data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
    _atomic_write_bytes(dest_abs, data)


def safe_resolve_under_data_dir(rel_path: str) -> Path:
    """
    Resolve a DB-stored relative path under `settings.data_dir`.

    This prevents accidental directory traversal if a row is corrupted.
    """
    base = Path(settings.data_dir).resolve()
    abs_path = (base / rel_path).resolve()
    try:
        abs_path.relative_to(base)
    except ValueError as e:
        raise ValueError(f"path is outside data_dir: {rel_path}") from e
    return abs_path

