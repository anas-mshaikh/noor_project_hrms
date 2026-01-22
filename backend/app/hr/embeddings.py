"""
HuggingFace-based text embeddings for HR resume search (Phase 2).

Why SentenceTransformers?
- It is a thin wrapper around HuggingFace models and makes model switching easy
  in the MVP (BGE-M3 now, other models later).

Operational notes:
- Model loading is lazy and cached (singleton per worker process).
- The model is stored/cached under `settings.hr_embed_cache_dir` (mounted in Docker).
- We always normalize embeddings so cosine distance is well-behaved.
̆̆"""

from __future__ import annotations

import numpy as np

from app.core.config import settings


class HREmbeddingModelError(RuntimeError):
    """
    Raised when the embedding model cannot be loaded or used.
    """


_MODEL = None


def _load_model():
    """
    Load the SentenceTransformer model once per process.

    We keep imports inside the function so the API process can start quickly even if
    embedding deps are not installed (the embedding worker will need them).
    """
    global _MODEL
    if _MODEL is not None:
        return _MODEL

    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except Exception as e:
        raise HREmbeddingModelError(
            "sentence-transformers is required for HR resume embeddings"
        ) from e

    # `cache_folder` keeps large model downloads out of container layers (mounted volume).
    model = SentenceTransformer(
        settings.hr_embed_model_name,
        device=settings.hr_embed_device,
        cache_folder=settings.hr_embed_cache_dir,
    )

    # BGE-M3 supports large context windows; keep this configurable.
    # Some SentenceTransformers versions/models may not allow setting this.
    try:
        model.max_seq_length = int(settings.hr_embed_max_seq_length)
    except Exception:
        pass

    _MODEL = model
    return model


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Embed a list of texts into 1024-d vectors.

    Returns a list of Python float lists so they can be stored directly in pgvector.
    """
    if not texts:
        return []

    model = _load_model()
    try:
        vecs = model.encode(  # type: ignore[attr-defined]
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
    except Exception as e:
        raise HREmbeddingModelError(f"embedding failed: {e}") from e

    # SentenceTransformers can return a numpy array or a list; normalize to numpy.
    arr = np.asarray(vecs, dtype=np.float32)
    if arr.ndim == 1:
        arr = arr.reshape(1, -1)

    # IMPORTANT: The DB column type is `vector(settings.hr_embed_dim)`.
    # If the model returns a different dimension, pgvector inserts will fail with
    # a confusing error. We raise a clear error instead.
    expected_dim = int(settings.hr_embed_dim)
    if arr.shape[1] != expected_dim:
        raise HREmbeddingModelError(
            "embedding dimension mismatch: "
            f"model returned dim={arr.shape[1]} but DB expects dim={expected_dim}. "
            "If you changed HR_EMBED_MODEL_NAME to a different model, create a migration "
            "to update `hr_resume_views.embedding` to the new vector dimension and update HR_EMBED_DIM."
        )

    return arr.astype(float).tolist()


def embed_text(text: str) -> list[float]:
    """
    Convenience wrapper for a single text.
    """
    return embed_texts([text])[0]
