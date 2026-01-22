"""
onboarding_storage.py (HR module - Phase 6)

Local storage helpers for onboarding document uploads.

Design principles (consistent with `app/hr/storage.py`):
- Store files under `settings.data_dir` so Docker volume mounts work.
- Persist *relative* paths in Postgres; resolve them under data_dir when reading.
- Sanitize filenames to prevent path traversal and weird filesystem edge cases.

Directory layout (all relative to settings.data_dir):
  hr/onboarding/{employee_id}/{document_id}/files/{filename}
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.hr.storage import sanitize_filename


@dataclass(frozen=True)
class OnboardingDocumentPaths:
    """
    Computed paths for a single onboarding document.

    We intentionally store only one file per document row in Phase 6.
    If you want versioning later, create new `hr_employee_documents` rows.
    """

    file_rel: str

    @property
    def file_abs(self) -> Path:
        return (Path(settings.data_dir) / self.file_rel).resolve()


def build_onboarding_document_paths(
    *, employee_id: UUID, document_id: UUID, original_filename: str
) -> OnboardingDocumentPaths:
    """
    Compute canonical on-disk paths for an onboarding document upload.
    """

    safe_name = sanitize_filename(original_filename, default="document")
    base = f"hr/onboarding/{employee_id}/{document_id}"
    return OnboardingDocumentPaths(file_rel=f"{base}/files/{safe_name}")

