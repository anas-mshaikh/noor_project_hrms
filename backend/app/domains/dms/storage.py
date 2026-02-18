"""
Local file storage abstraction for the DMS module.

Milestone 5 requirements:
- LOCAL storage provider in v1 (S3 can be added later without schema churn)
- Store relative "object_key" paths in Postgres (under settings.data_dir)
- Prevent path traversal and write files atomically

We reuse hardened helpers from `app.hr.storage`:
- sanitize_filename(...) for safe basenames
- safe_resolve_under_data_dir(...) to ensure DB-stored paths stay under data_dir
"""

from __future__ import annotations


import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from app.core.config import settings
from app.hr.storage import sanitize_filename, safe_resolve_under_data_dir


@dataclass(frozen=True)
class SaveResult:
    """
    Result of saving a file to storage.
    """

    size_bytes: int
    sha256: str


class StorageProvider(Protocol):
    """
    Storage provider interface.

    Providers must:
    - write files under settings.data_dir (for LOCAL) or a stable remote key (for S3)
    - be safe against path traversal
    """

    def save_upload(self, *, upload_file, object_key: str) -> SaveResult: ...

    def resolve_abs_path(self, *, object_key: str) -> Path: ...

    def delete(self, *, object_key: str) -> None: ...


class LocalStorageProvider:
    """
    Simple LOCAL filesystem provider.

    Layout (relative to settings.data_dir):
      dms/files/{tenant_id}/{file_id}/{safe_filename}
    """

    def build_object_key(
        self, *, tenant_id: UUID, file_id: UUID, original_filename: str
    ) -> str:
        safe_name = sanitize_filename(original_filename, default="file")
        return f"dms/files/{tenant_id}/{file_id}/{safe_name}"

    def resolve_abs_path(self, *, object_key: str) -> Path:
        # We store `object_key` as a relative path in Postgres.
        return safe_resolve_under_data_dir(object_key)

    def save_upload(self, *, upload_file, object_key: str) -> SaveResult:
        """
        Stream an UploadFile-like object to disk.

        Implementation details:
        - writes to "<dest>.part" then renames (atomic on POSIX)
        - computes sha256 while streaming (useful for debugging/audit)
        """

        dest_abs = self.resolve_abs_path(object_key=object_key)
        dest_abs.parent.mkdir(parents=True, exist_ok=True)

        tmp_abs = dest_abs.with_suffix(dest_abs.suffix + ".part")
        h = hashlib.sha256()
        size = 0

        try:
            with tmp_abs.open("wb") as out:
                while True:
                    chunk = upload_file.file.read(1024 * 1024)
                    if not chunk:
                        break
                    out.write(chunk)
                    h.update(chunk)
                    size += len(chunk)

            tmp_abs.replace(dest_abs)
            return SaveResult(size_bytes=size, sha256=h.hexdigest())
        finally:
            # UploadFile holds an underlying file handle; close it to release resources.
            try:
                upload_file.file.close()
            except Exception:
                pass

            # Best-effort cleanup for partial writes.
            if tmp_abs.exists():
                try:
                    tmp_abs.unlink()
                except Exception:
                    pass

    def delete(self, *, object_key: str) -> None:
        """
        Best-effort physical delete (v1 uses soft delete in DB).
        """

        try:
            path = self.resolve_abs_path(object_key=object_key)
        except Exception:
            return
        if not path.exists():
            return
        if path.is_file():
            try:
                path.unlink()
            except Exception:
                # Non-fatal in v1; DB status is the source of truth for access.
                return


def get_storage_provider(storage_provider: str) -> StorageProvider:
    """
    Resolve a storage provider by code stored in dms.files.storage_provider.

    v1 supports LOCAL only. We keep the switch for forward compatibility.
    """

    if (storage_provider or "").upper() in ("LOCAL", ""):
        return LocalStorageProvider()

    # Keep the failure explicit; callers can map this to AppError if needed.
    raise ValueError(f"Unsupported storage_provider: {storage_provider!r}")


def ensure_dms_root() -> None:
    """
    Ensure the base DMS directory exists under the configured data_dir.

    This is safe to call at import/startup time.
    """

    Path(settings.data_dir).resolve().joinpath("dms").mkdir(parents=True, exist_ok=True)
