"""
face_system_smoke_test.py

Small, local smoke test for the Frigate-style face subsystem.

This script intentionally does NOT require the FastAPI server or the database.
It works purely on disk images and the in-memory prototype recognizer.

Usage (from repo root):
  PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend .venv/bin/python \\
    backend/scripts/face_system_smoke_test.py \\
    --store-id <uuid> \\
    --employee-id <uuid> \\
    --train path/to/img1.jpg path/to/img2.jpg \\
    --query path/to/query.jpg

What it does:
1) Loads face models (FaceDetectorYN + ArcFace ONNX)
2) Detects + crops the best face in each --train image
3) Saves the cropped faces into: backend/data/faces/<store>/<employee>/
4) Rebuilds prototypes
5) Runs recognition on --query and prints the best match + topK list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from uuid import UUID


def _ensure_backend_on_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    backend_dir = repo_root / "backend"
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))


def _read_bgr(path: Path):
    try:
        import cv2  # type: ignore
    except Exception as e:
        raise SystemExit(f"opencv-python is required: {e}") from e

    img = cv2.imread(str(path))
    if img is None:
        raise SystemExit(f"Could not read image: {path}")
    return img


def main() -> int:
    _ensure_backend_on_path()

    from app.face_system.runtime_processor import get_runtime_processor
    from app.face_system.storage import FaceLibraryStorage

    parser = argparse.ArgumentParser()
    parser.add_argument("--store-id", required=True)
    parser.add_argument("--employee-id", required=True)
    parser.add_argument("--train", nargs="+", required=True, help="Training images (2+)")
    parser.add_argument("--query", required=True, help="Query image")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args()

    store_id = UUID(args.store_id)
    employee_id = UUID(args.employee_id)

    proc = get_runtime_processor(store_id=store_id, camera_id=None)
    storage = FaceLibraryStorage(proc.cfg.storage)

    print(f"Store:    {store_id}")
    print(f"Employee: {employee_id}")
    print(f"Face dir: {storage.face_dir}")

    # Register training images by detecting + cropping the best face.
    for p in args.train:
        path = Path(p)
        img = _read_bgr(path)
        det = proc.detector.detect_best(img)
        if det is None:
            raise SystemExit(f"No face detected in training image: {path}")
        x1, y1, x2, y2 = det.bbox_xyxy
        face_crop = img[y1:y2, x1:x2].copy()
        if face_crop.size == 0:
            raise SystemExit(f"Invalid face crop from training image: {path}")

        stored = storage.save_face_crop(
            store_id=store_id,
            employee_id=employee_id,
            face_crop_bgr=face_crop,
            ext=path.suffix or ".jpg",
        )
        print(f"Saved training crop: {stored.rel_path}")

    # Rebuild prototypes (blocking).
    proc.recognizer.clear()
    proc.recognizer.ensure_built(block=True, timeout_sec=60.0)
    stats = proc.recognizer.stats()
    print(f"Prototypes built: {stats.employees if stats else 0} employees, {stats.images if stats else 0} images")

    # Recognize query.
    query_img = _read_bgr(Path(args.query))
    result = proc.recognizer.recognize_image(query_img, top_k=int(args.top_k))

    print("\nBest match:")
    print(f"  employee_id: {result.employee_id}")
    print(f"  confidence:  {result.confidence:.4f}")
    print(f"  cos_sim:     {result.cosine_similarity}")

    print("\nTop-K:")
    for m in result.top_k:
        print(f"  {m.employee_id}  sim={m.cosine_similarity:.4f}  conf={m.confidence:.4f}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

