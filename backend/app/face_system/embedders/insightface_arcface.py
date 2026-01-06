"""
insightface_arcface.py

ArcFace-style embedding model using ONNXRuntime.

We intentionally keep this independent from InsightFace FaceAnalysis, because:
- face detection is handled separately (FaceDetectorYN)
- alignment is handled separately (FacemarkLBF)
- embedding should be a simple, swappable component

Default model path points at InsightFace buffalo_l recognition model:
  <INSIGHTFACE_ROOT>/models/<FACE_MODEL_NAME>/w600k_r50.onnx
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from app.face_system.config import FaceEmbedderConfig
from app.face_system.utils import l2_normalize


class FaceSystemModelError(RuntimeError):
    pass


@dataclass
class _EmbedderState:
    session: object
    input_name: str


class ONNXArcFaceEmbedder:
    def __init__(self, cfg: FaceEmbedderConfig) -> None:
        self._cfg = cfg
        self._state: _EmbedderState | None = None

    def _ensure_loaded(self) -> _EmbedderState:
        if self._state is not None:
            return self._state

        model_path = Path(self._cfg.model_path).expanduser().resolve()
        if not model_path.exists():
            raise FaceSystemModelError(f"embedding model missing: {model_path}")

        try:
            import onnxruntime as ort  # type: ignore
        except Exception as e:
            raise FaceSystemModelError(
                "onnxruntime is required for ArcFace embeddings."
            ) from e

        sess = ort.InferenceSession(
            str(model_path),
            providers=["CPUExecutionProvider"],
        )

        inputs = sess.get_inputs()
        if not inputs:
            raise FaceSystemModelError("embedding model has no inputs")

        input_name = str(inputs[0].name)
        self._state = _EmbedderState(session=sess, input_name=input_name)
        return self._state

    def embed(self, face_bgr: np.ndarray) -> np.ndarray:
        state = self._ensure_loaded()

        import cv2  # type: ignore

        img = face_bgr

        # Resize to model input.
        img = cv2.resize(
            img,
            (int(self._cfg.input_width), int(self._cfg.input_height)),
            interpolation=cv2.INTER_CUBIC,
        )

        # ArcFace models typically expect RGB with normalization to [-1, 1].
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = img.astype(np.float32)
        img = (img - 127.5) / 127.5

        # NCHW
        blob = np.transpose(img, (2, 0, 1))[None, :, :, :]

        # Run ONNX
        outputs = state.session.run(None, {state.input_name: blob})  # type: ignore[attr-defined]
        if not outputs:
            raise FaceSystemModelError("embedding model returned no outputs")

        emb = np.asarray(outputs[0]).astype(np.float32).reshape(-1)
        if emb.shape[0] != 512:
            # Some models may output 256/1024; but our system expects 512.
            raise FaceSystemModelError(
                f"unexpected embedding dim: {emb.shape[0]} (expected 512)"
            )

        return l2_normalize(emb)

