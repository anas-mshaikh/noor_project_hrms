"""
Why this design:

init creates the DB row and decides the final storage path (no path
traversal issues).
upload writes to *.part and then atomically renames → avoids partial file
corruption.
finalize computes sha256 (useful for dedupe/audit); worker can fill fps/
duration later.
"""

import json
import subprocess
from fractions import Fraction
from typing import Any

import hashlib
from datetime import date, datetime
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, File, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import require_permission
from app.auth.permissions import VISION_VIDEO_UPLOAD
from app.core.config import settings
from app.core.errors import AppError
from app.core.responses import ok
from app.db.session import get_db
from app.models.models import Camera, Video
from app.shared.types import AuthContext

router = APIRouter(tags=["videos"])


ALLOWED_VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi"}


def _safe_ext(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return ext if ext in ALLOWED_VIDEO_EXTS else ".mp4"


def _video_rel_path(
    tenant_id: UUID, branch_id: UUID, camera_id: UUID, business_date: date, filename: str
) -> str:
    ext = _safe_ext(filename)
    return f"videos/{tenant_id}/{branch_id}/{camera_id}/{business_date.isoformat()}/original{ext}"


def _full_path(rel_path: str) -> Path:
    return Path(settings.data_dir) / rel_path


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _parse_rate(rate: str | None) -> float | None:
    """
    ffprobe returns fps as a fraction string (e.g. "30000/1001").
    """
    if not rate:
        return None
    try:
        return float(Fraction(rate))
    except Exception:
        return None


def _ffprobe_video(path: Path) -> dict[str, Any]:
    """
    Uses ffprobe to extract video metadata.
    ffprobe must be installed on the server (it’s part of ffmpeg).
    """
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,avg_frame_rate,r_frame_rate,duration:format=duration",
        "-of",
        "json",
        str(path),
    ]
    out = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return json.loads(out.stdout)


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
    "/branches/{branch_id}/videos/init",
    status_code=status.HTTP_201_CREATED,
)
def init_video_upload(
    branch_id: UUID,
    body: VideoInitRequest,
    ctx: AuthContext = Depends(require_permission(VISION_VIDEO_UPLOAD)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    camera = (
        db.query(Camera)
        .filter(
            Camera.id == body.camera_id,
            Camera.tenant_id == ctx.scope.tenant_id,
            Camera.branch_id == branch_id,
        )
        .first()
    )
    if camera is None:
        raise AppError(code="vision.camera.not_found", message="Camera not found", status_code=404)

    rel_path = _video_rel_path(
        ctx.scope.tenant_id, branch_id, body.camera_id, body.business_date, body.filename
    )

    video = Video(
        tenant_id=ctx.scope.tenant_id,
        branch_id=branch_id,
        camera_id=body.camera_id,
        business_date=body.business_date,
        file_path=rel_path,
        uploaded_by=body.uploaded_by,
        recorded_start_ts=body.recorded_start_ts,
    )

    db.add(video)
    db.commit()
    db.refresh(video)

    return ok(
        VideoInitResponse(
            video_id=video.id,
            file_path=video.file_path,
            upload_endpoint=f"{settings.api_v1_prefix}/branches/{branch_id}/videos/{video.id}/file",
            finalize_endpoint=f"{settings.api_v1_prefix}/branches/{branch_id}/videos/{video.id}/finalize",
        ).model_dump()
    )


@router.put("/branches/{branch_id}/videos/{video_id}/file")
def upload_video_file(
    branch_id: UUID,
    video_id: UUID,
    file: UploadFile = File(...),
    ctx: AuthContext = Depends(require_permission(VISION_VIDEO_UPLOAD)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    video = (
        db.query(Video)
        .filter(
            Video.id == video_id,
            Video.tenant_id == ctx.scope.tenant_id,
            Video.branch_id == branch_id,
        )
        .first()
    )
    if video is None:
        raise AppError(code="vision.video.not_found", message="Video not found", status_code=404)

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

    return ok(
        {
            "status": "uploaded",
            "file_path": video.file_path,
            "bytes": dest.stat().st_size,
        }
    )


@router.post("/branches/{branch_id}/videos/{video_id}/finalize")
def finalize_video(
    branch_id: UUID,
    video_id: UUID,
    ctx: AuthContext = Depends(require_permission(VISION_VIDEO_UPLOAD)),
    db: Session = Depends(get_db),
) -> dict[str, object]:
    video = (
        db.query(Video)
        .filter(
            Video.id == video_id,
            Video.tenant_id == ctx.scope.tenant_id,
            Video.branch_id == branch_id,
        )
        .first()
    )
    if video is None:
        raise AppError(code="vision.video.not_found", message="Video not found", status_code=404)

    path = _full_path(video.file_path)
    if not path.exists():
        raise AppError(
            code="vision.video.file_not_uploaded",
            message="Video file not uploaded yet",
            status_code=400,
        )

    video.sha256 = _sha256_file(path)

    # Fill metadata (best-effort).
    # If ffprobe fails, we keep sha256 but don't block finalize.
    try:
        meta = _ffprobe_video(path)
        streams = meta.get("streams") or []
        stream0 = streams[0] if streams else {}
        fmt = meta.get("format") or {}

        video.width = stream0.get("width")
        video.height = stream0.get("height")

        fps = _parse_rate(stream0.get("avg_frame_rate")) or _parse_rate(
            stream0.get("r_frame_rate")
        )
        video.fps = fps

        dur = stream0.get("duration") or fmt.get("duration")
        video.duration_sec = float(dur) if dur is not None else None
    except Exception:
        # Keep finalize robust during local dev; you can log this later if needed.
        pass

    db.commit()
    db.refresh(video)

    return ok(
        {
            "video_id": str(video.id),
            "sha256": video.sha256,
            "file_path": video.file_path,
            "fps": video.fps,
            "duration_sec": video.duration_sec,
            "width": video.width,
            "height": video.height,
        }
    )
