"""
detector_tracker.py

Ultralytics YOLO person detection + ByteTrack tracking.

This is a real implementation (no stubs):
- Requires local YOLO weights (.pt)
- Produces stable track IDs while persist=True
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import numpy as np

from app.core.config import settings


@dataclass(frozen=True)
class TrackedPerson:
    track_id: int
    bbox_xyxy: tuple[float, float, float, float]
    conf: float


class DetectorTracker:
    def __init__(
        self,
        *,
        model_path: str | None = None,
        imgsz: int | None = None,
        conf: float | None = None,
        iou: float | None = None,
        tracker: str | None = None,
    ) -> None:
        model_path = model_path or settings.yolo_model_path
        imgsz = int(imgsz or settings.yolo_imgsz)
        conf = float(conf or settings.yolo_conf)
        iou = float(iou or settings.yolo_iou)
        tracker = tracker or settings.yolo_tracker
        
        self._imgsz = imgsz
        self._conf = conf
        self._iou = iou
        self._tracker = tracker

        p = Path(model_path)
        if not p.exists():
            raise RuntimeError(
                f"YOLO weights not found: {p}. Set YOLO_MODEL_PATH to a local .pt file."
            )

        try:
            from ultralytics import YOLO  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "ultralytics is required for YOLO+ByteTrack. Install it via requirements.txt."
            ) from e

        self._model = YOLO(str(p))
    
    def track(self, frame_bgr: np.ndarray) -> list[TrackedPerson]:
        results = self._model.track(
            frame_bgr,
            persist=True,
            verbose=False,
            imgsz=self._imgsz,
            conf=self._conf,
            iou=self._iou,
            classes=[0],  # person
            tracker=self._tracker,
        )

        if not results:
            return []

        r0 = results[0]
        boxes = getattr(r0, "boxes", None)
        if boxes is None:
            return []

        ids = getattr(boxes, "id", None)
        xyxy = getattr(boxes, "xyxy", None)
        conf = getattr(boxes, "conf", None)
        if ids is None or xyxy is None:
            return []
        
        ids_np = ids.detach().cpu().numpy().astype(int)
        xyxy_np = xyxy.detach().cpu().numpy().astype(float)

        if conf is not None:
            conf_np = conf.detach().cpu().numpy().astype(float)
        else:
            conf_np = np.ones((len(ids_np),), dtype=float)

        out: list[TrackedPerson] = []
        for i in range(len(ids_np)):
            tid = int(ids_np[i])
            x1, y1, x2, y2 = xyxy_np[i].tolist()
            out.append(
                TrackedPerson(
                    track_id=tid,
                    bbox_xyxy=(float(x1), float(y1), float(x2), float(y2)),
                    conf=float(conf_np[i]),
                )
            )
        return out

