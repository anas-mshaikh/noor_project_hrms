"""
Local reranker utility for the HR module (Phase 3).

We use a BGE reranker (cross-encoder style) to re-score a *candidate pool* of resumes
retrieved by embedding similarity.

Why a reranker?
- Embedding retrieval is great for recall (fast approximate matching) but can be noisy.
- A reranker reads the query + document together and can make more precise judgments.

Design goals:
- Keep everything **local** (no external services).
- Lazy-load the model once per worker process (like our embedding loader).
- Batch inference to avoid memory spikes and to keep performance acceptable on CPU.
"""

from __future__ import annotations

import os
from typing import Iterable

from app.core.config import settings


class HRRerankerError(RuntimeError):
    """
    Raised when the reranker cannot be loaded or used.
    """


_RERANKER = None


def _load_reranker():
    """
    Load the reranker model once per process.

    We keep imports inside the function so the API server can start without the
    reranker dependencies installed (only the HR worker needs them).
    """
    global _RERANKER
    if _RERANKER is not None:
        return _RERANKER

    if not settings.hr_rerank_enabled:
        raise HRRerankerError("HR reranker is disabled (HR_RERANK_ENABLED=false)")

    try:
        # FlagEmbedding provides a convenient wrapper around BGE rerankers.
        # https://pypi.org/project/FlagEmbedding/ (docs referenced in upstream examples)
        from FlagEmbedding import FlagReranker  # type: ignore
    except Exception as e:
        raise HRRerankerError(
            "FlagEmbedding is required for HR reranking (install FlagEmbedding)"
        ) from e

    # Keep HuggingFace caches inside a mounted volume when running in Docker.
    # This avoids re-downloading the model every time containers restart.
    #
    # If the environment already sets HF_HOME/TRANSFORMERS_CACHE explicitly,
    # we do not override it.
    os.environ.setdefault("HF_HOME", settings.hr_embed_cache_dir)
    os.environ.setdefault("TRANSFORMERS_CACHE", settings.hr_embed_cache_dir)

    # FlagEmbedding's reranker supports FP16 on GPU. For CPU-only deployments we
    # keep fp16 disabled to avoid errors and to keep determinism.
    #
    # NOTE: if you add GPU support later, you can make this configurable.
    use_fp16 = False

    reranker = FlagReranker(settings.hr_reranker_model_name, use_fp16=use_fp16)
    _RERANKER = reranker
    return reranker


def rerank_pairs(query: str, docs: list[str], *, batch_size: int | None = None) -> list[float]:
    """
    Rerank a set of documents against a single query.

    Returns a list of floats aligned with `docs` (higher is better).

    Implementation notes:
    - We run in batches because cross-encoders are heavier than embeddings.
    - We support multiple FlagEmbedding reranker APIs defensively (`compute_score` vs `score`)
      so we don't get stuck on minor upstream version differences.
    """
    if not docs:
        return []

    reranker = _load_reranker()
    bs = max(1, int(batch_size or settings.hr_reranker_batch_size))

    scores: list[float] = []
    pairs: list[list[str]] = [[query, d] for d in docs]

    for i in range(0, len(pairs), bs):
        chunk = pairs[i : i + bs]
        chunk_scores = _compute_scores(reranker, chunk, query=query)

        # Normalize to float list (FlagEmbedding may return numpy types).
        scores.extend([float(s) for s in chunk_scores])

    return scores


def _compute_scores(reranker, pairs: list[list[str]], *, query: str) -> Iterable[float]:
    """
    Compute scores for (query, doc) pairs using a FlagEmbedding reranker instance.

    We keep this as a small adapter to tolerate upstream API differences.
    """
    if hasattr(reranker, "compute_score"):
        # Common FlagEmbedding API: reranker.compute_score([[q, d], ...])
        return reranker.compute_score(pairs)  # type: ignore[attr-defined]

    if hasattr(reranker, "compute_scores"):
        return reranker.compute_scores(pairs)  # type: ignore[attr-defined]

    if hasattr(reranker, "score"):
        # Some wrappers expose a `score` method. It may accept either:
        # - a list of pairs, OR
        # - (query, docs)
        try:
            return reranker.score(pairs)  # type: ignore[attr-defined]
        except TypeError:
            return reranker.score(query, [d for _q, d in pairs])  # type: ignore[attr-defined]

    raise HRRerankerError("Unsupported reranker interface (FlagEmbedding API changed?)")

