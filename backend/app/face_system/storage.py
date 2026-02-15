"""
storage.py

File-based face library storage (Frigate-style).

Directory layout:
  <FACE_DIR>/<tenant_id>/<branch_id>/<employee_id>/*.jpg

This is separate from the DB (pgvector) templates:
- You can still keep pgvector for "search by face" debug tools.
- The runtime recognizer uses prototypes built from these training images.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

import numpy as np

from app.face_system.config import FaceStorageConfig
from app.face_system.utils import safe_basename


@dataclass(frozen=True)
class StoredFaceImage:
    filename: str
    rel_path: str


class FaceLibraryStorage:
    def __init__(self, cfg: FaceStorageConfig) -> None:
        self._cfg = cfg

    @property
    def face_dir(self) -> Path:
        return self._cfg.face_dir

    def employee_dir(self, *, tenant_id: UUID, branch_id: UUID, employee_id: UUID) -> Path:
        return self._cfg.face_dir / str(tenant_id) / str(branch_id) / str(employee_id)

    def list_employee_images(
        self, *, tenant_id: UUID, branch_id: UUID, employee_id: UUID
    ) -> list[StoredFaceImage]:
        d = self.employee_dir(tenant_id=tenant_id, branch_id=branch_id, employee_id=employee_id)
        if not d.exists():
            return []
        out: list[StoredFaceImage] = []
        for p in sorted(d.glob("*")):
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                rel = str(p.relative_to(self._cfg.face_dir))
                out.append(StoredFaceImage(filename=p.name, rel_path=rel))
        return out

    def delete_employee_image(
        self, *, tenant_id: UUID, branch_id: UUID, employee_id: UUID, filename: str
    ) -> bool:
        d = self.employee_dir(tenant_id=tenant_id, branch_id=branch_id, employee_id=employee_id)
        fn = safe_basename(filename)
        p = d / fn
        if not p.exists():
            return False
        p.unlink()
        return True

    def save_face_crop(
        self,
        *,
        tenant_id: UUID,
        branch_id: UUID,
        employee_id: UUID,
        face_crop_bgr: np.ndarray,
        ext: str = ".jpg",
    ) -> StoredFaceImage:
        """
        Save a cropped face image for training.
        """
        # Lazy import (OpenCV is already required by the project).
        import cv2  # type: ignore

        ext = ext.lower().strip()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            ext = ".jpg"

        d = self.employee_dir(tenant_id=tenant_id, branch_id=branch_id, employee_id=employee_id)
        d.mkdir(parents=True, exist_ok=True)

        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        filename = f"{ts}{ext}"
        abs_path = d / filename

        cv2.imwrite(str(abs_path), face_crop_bgr)

        rel = str(abs_path.relative_to(self._cfg.face_dir))
        return StoredFaceImage(filename=filename, rel_path=rel)

    def branch_has_any_images(self, *, tenant_id: UUID, branch_id: UUID) -> bool:
        branch_dir = self._cfg.face_dir / str(tenant_id) / str(branch_id)
        if not branch_dir.exists():
            return False
        for p in branch_dir.rglob("*"):
            if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                return True
        return False
