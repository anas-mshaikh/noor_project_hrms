"""
Why this design:

init creates the DB row and decides the final storage path (no path
traversal issues).
upload writes to *.part and then atomically renames → avoids partial file
corruption.
finalize computes sha256 (useful for dedupe/audit); worker can fill fps/
duration later.
"""

import hashlib
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models.models import Camera, Video

router = APIRouter(tags=["videos"])


ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi"}


def _safe_ext(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return ext if ext in ALLOWED_VIDEO_EXTS else ".mp4"


def _video_rel_path(
    store_id: UUID, camera_id: UUID, business_date: date, filename: str
) -> str:
    ext = _safe_ext(filename)
    return f"videos/{store_id}/{camera_id}/{business_date.isoformat()}/original{ext}"


def _full_path(rel_path: str) -> Path:
    return Path(settings.data_dir) / rel_path


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


class VideoInitRequest(BaseModel):
    camera_id: UUID
    business_date: date
    filename: str
    uploaded_by: str | None = None
    recorded_start_ts: datetime | None = None


class VideoInitResponse(BaseModel):
    video_id: UUID
    file_path: str
    upload_endpoint: str
    finalize_endpoint: str


@router.post(
    "/stores/{store_id}/videos/init",
    response_model=VideoInitResponse,
    status_code=status.HTTP_201_CREATED,
)
def init_video_upload(
    store_id: UUID,
    body: VideoInitRequest,
    db: Session = Depends(get_db),
) -> VideoInitResponse:
    camera = db.get(Camera, body.camera_id)
    if camera is None or camera.store_id != store_id:
        raise HTTPException(status_code=404, detail="Camera not found for store")

    rel_path = _video_rel_path(
        store_id, body.camera_id, body.business_date, body.filename
    )

    video = Video(
        store_id=store_id,
        camera_id=body.camera_id,
        business_date=body.business_date,
        file_path=rel_path,
        uploaded_by=body.uploaded_by,
        recorded_start_ts=body.recorded_start_ts,
    )

    db.add(video)
    db.commit()
    db.refresh(video)

    return VideoInitResponse(
        video_id=video.id,
        file_path=video.file_path,
        upload_endpoint=f"{settings.api_v1_prefix}/stores/{store_id}/videos/{video.id}/file",
        finalize_endpoint=f"{settings.api_v1_prefix}/stores/{store_id}/videos/{video.id}/finalize",
    )


@router.put("/stores/{store_id}/videos/{video_id}/file")
def upload_video_file(
    store_id: UUID,
    video_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    video = db.get(Video, video_id)
    if video is None or video.store_id != store_id:
        raise HTTPException(status_code=404, detail="Video not found for store")

    dest = _full_path(video.file_path)
    dest.parent.mkdir(parents=True, exist_ok=True)

    tmp = dest.with_suffix(dest.suffix + ".part")
    try:
        with tmp.open("wb") as out:
            while True:
                chunk = file.file.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
        tmp.replace(dest)
    finally:
        file.file.close()

    return {
        "status": "uploaded",
        "file_path": video.file_path,
        "bytes": dest.stat().st_size,
    }


@router.post("/stores/{store_id}/videos/{video_id}/finalize")
def finalize_video(
    store_id: UUID,
    video_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    video = db.get(Video, video_id)
    if video is None or video.store_id != store_id:
        raise HTTPException(status_code=404, detail="Video not found for store")

    path = _full_path(video.file_path)
    if not path.exists():
        raise HTTPException(status_code=400, detail="Video file not uploaded yet")

    video.sha256 = _sha256_file(path)
    db.commit()
    db.refresh(video)

    return {
        "video_id": str(video.id),
        "sha256": video.sha256,
        "file_path": video.file_path,
    }
