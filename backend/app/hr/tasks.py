"""
RQ background tasks for the HR module.

Phase 1 requirement:
- Parse uploaded resumes using the `unstructured` library.
- Store parsed artifacts locally (parsed.json + clean.txt).
- Persist status/error updates in Postgres (source of truth).

Phase 2 additions:
- Build multiple resume "views" (full/skills/experience).
- Embed those views using a local HuggingFace model (BGE-M3 by default).
- Store embeddings in Postgres (pgvector) for later retrieval/ranking.

Notes:
- We import `unstructured` lazily so the API can start even if parsing deps are missing.
- We keep parsing best-effort: if an element can't be serialized, we store minimal info.
"""

from __future__ import annotations

import uuid
import logging
import math
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal
from app.hr.storage import build_resume_paths, safe_resolve_under_data_dir, write_json, write_text
from app.models.models import (
    HROpening,
    HRResume,
    HRResumeView,
    HRScreeningRun,
    HRScreeningResult,
    HRScreeningExplanation,
)


logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _sigmoid(x: float) -> float:
    """
    Stable sigmoid for turning reranker logits into a 0..1 score.

    Notes:
    - BGE rerankers typically output a raw, unbounded logit that can be negative.
    - Sigmoid preserves ordering (monotonic), so ranking is stable and reproducible.
    """
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def _clamp01(x: float) -> float:
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _elements_to_dicts(elements: list[Any]) -> list[dict[str, Any]]:
    """
    Convert Unstructured elements to JSON-serializable dictionaries.
    """
    out: list[dict[str, Any]] = []
    for el in elements:
        # Unstructured elements typically provide to_dict().
        if hasattr(el, "to_dict"):
            try:
                out.append(el.to_dict())  # type: ignore[call-arg]
                continue
            except Exception:
                pass

        # Fallback: capture only text + type.
        text = getattr(el, "text", None)
        out.append({"type": type(el).__name__, "text": text})
    return out


def _elements_to_clean_text(elements: list[Any]) -> str:
    """
    Convert elements into a single clean text string for quick human inspection.
    """
    lines: list[str] = []
    for el in elements:
        text = getattr(el, "text", None)
        if not text:
            continue
        t = str(text).strip()
        if not t:
            continue
        lines.append(t)
    return "\n".join(lines).strip()


def _partition_resume(file_path: Path) -> list[Any]:
    """
    Parse a resume file using Unstructured.

    We avoid relying on libmagic-based filetype detection (which can require extra
    OS packages in slim Docker images) by choosing partitioners based on extension.
    """
    try:
        # Note: unstructured is an optional dependency for the API process; this task
        # will raise a clear error if it's not installed in the worker environment.
        from unstructured.partition.auto import partition  # type: ignore
    except Exception:
        partition = None

    suffix = file_path.suffix.lower()

    # Prefer extension-specific partitioners first (more deterministic).
    try:
        if suffix == ".pdf":
            from unstructured.partition.pdf import partition_pdf  # type: ignore

            return partition_pdf(filename=str(file_path))
        if suffix in {".docx", ".doc"}:
            from unstructured.partition.docx import partition_docx  # type: ignore

            return partition_docx(filename=str(file_path))
        if suffix in {".txt", ".md"}:
            from unstructured.partition.text import partition_text  # type: ignore

            return partition_text(filename=str(file_path))
    except Exception:
        # We'll fall back to auto partition below.
        pass

    if partition is None:
        raise RuntimeError(
            "unstructured is required to parse resumes (missing dependency)"
        )

    return partition(filename=str(file_path))


def _set_resume(db: Session, resume: HRResume, **fields) -> None:
    """
    Convenience helper to commit status transitions consistently.
    """
    for k, v in fields.items():
        setattr(resume, k, v)
    resume.updated_at = _utcnow()
    db.add(resume)
    db.commit()
    db.refresh(resume)


def parse_resume(resume_id: str) -> None:
    """
    RQ job entrypoint: parse one resume and write artifacts to disk.

    Idempotency:
    - If already PARSED and parsed_path exists on disk, we do nothing.
    """
    resume_uuid = UUID(resume_id)
    db = SessionLocal()
    try:
        resume = db.get(HRResume, resume_uuid)
        if resume is None:
            return

        if resume.status == "PARSED" and resume.parsed_path:
            parsed_abs = safe_resolve_under_data_dir(resume.parsed_path)
            if parsed_abs.exists():
                # Parsing is already done. If embeddings are enabled but not yet done,
                # enqueue embedding so Phase 2 can be rolled out to existing resumes.
                if settings.hr_embeddings_enabled and resume.embedding_status != "EMBEDDED":
                    from app.hr.queue import get_hr_queue

                    get_hr_queue().enqueue(embed_resume, str(resume.id))
                return

        # Mark as parsing early (source-of-truth for UI polling).
        _set_resume(db, resume, status="PARSING", error=None)

        raw_abs = safe_resolve_under_data_dir(resume.file_path)
        if not raw_abs.exists():
            raise FileNotFoundError(f"resume file missing: {resume.file_path}")

        # Parse + normalize artifacts.
        elements = _partition_resume(raw_abs)
        clean_text = _elements_to_clean_text(elements)
        elements_dicts = _elements_to_dicts(elements)

        paths = build_resume_paths(
            opening_id=resume.opening_id,
            resume_id=resume.id,
            original_filename=resume.original_filename,
        )

        # Persist artifacts (relative paths stored in DB).
        write_json(
            paths.parsed_json_abs,
            {
                "resume_id": str(resume.id),
                "opening_id": str(resume.opening_id),
                "tenant_id": str(resume.tenant_id),
                "company_id": str(resume.company_id),
                "branch_id": str(resume.branch_id),
                "parsed_at": _utcnow().isoformat(),
                "elements": elements_dicts,
                "clean_text": clean_text,
                "metadata": {
                    "filename": resume.original_filename,
                    "source_path": resume.file_path,
                },
            },
        )
        write_text(paths.clean_text_abs, clean_text)

        _set_resume(
            db,
            resume,
            status="PARSED",
            parsed_path=paths.parsed_json_rel,
            clean_text_path=paths.clean_text_rel,
            error=None,
            # Phase 2: embedding should run on the latest parsed output.
            embedding_status="PENDING",
            embedding_error=None,
            embedded_at=None,
        )

        # Phase 2: automatically enqueue embeddings after parsing completes.
        #
        # We keep this behind a feature flag so you can disable embeddings without
        # changing parsing behavior.
        if settings.hr_embeddings_enabled:
            # Import locally to avoid circular imports and to keep API startup fast.
            from app.hr.queue import get_hr_queue

            get_hr_queue().enqueue(embed_resume, str(resume.id))

    except Exception as e:
        # If any DB write failed before the exception bubbled, reset the session state.
        try:
            db.rollback()
        except Exception:
            pass

        # Store a compact, human-readable error in DB. Full traceback is still visible
        # in worker logs and in RQ's FailedJobRegistry.
        resume = db.get(HRResume, resume_uuid)
        if resume is not None:
            err = f"{type(e).__name__}: {e}"
            _set_resume(db, resume, status="FAILED", error=err)
        # Re-raise so RQ marks the job failed (useful for debugging).
        raise
    finally:
        db.close()


def embed_resume(resume_id: str) -> None:
    """
    RQ job entrypoint: build resume views and store embeddings in Postgres.

    Guardrails:
    - The resume must already be PARSED (text artifacts exist).
    - The task is idempotent: if the "full" text hash matches and an embedding exists,
      we skip re-embedding.
    """
    if not settings.hr_embeddings_enabled:
        return

    resume_uuid = UUID(resume_id)
    db = SessionLocal()
    try:
        resume = db.get(HRResume, resume_uuid)
        if resume is None:
            return

        if resume.status != "PARSED":
            # Parsing hasn't completed (or failed). Embedding depends on clean text.
            return

        # Build views from disk artifacts.
        from app.hr.views import build_resume_views, text_hash

        views = build_resume_views(resume)
        full_text = views.get("full", "")
        if not full_text.strip():
            raise RuntimeError("resume clean text is empty; cannot embed")

        full_hash = text_hash(full_text)

        # Idempotency check: if the stored full view hash matches and an embedding exists,
        # assume other derived views are also up-to-date (they are derived from `full`).
        existing_full = (
            db.query(HRResumeView)
            .filter(HRResumeView.resume_id == resume.id, HRResumeView.view_type == "full")
            .first()
        )
        if (
            existing_full is not None
            and existing_full.text_hash == full_hash
            and existing_full.embedding is not None
            and resume.embedding_status == "EMBEDDED"
        ):
            return

        _set_resume(db, resume, embedding_status="EMBEDDING", embedding_error=None)

        # Embed all views in one batch for efficiency.
        view_items = list(views.items())  # preserves insertion order (full first)
        from app.hr.embeddings import embed_texts

        vectors = embed_texts([txt for _vt, txt in view_items])

        for (view_type, txt), vec in zip(view_items, vectors):
            h = text_hash(txt)
            token_estimate = len(txt.split())

            row = (
                db.query(HRResumeView)
                .filter(
                    HRResumeView.resume_id == resume.id,
                    HRResumeView.view_type == view_type,
                )
                .first()
            )
            if row is None:
                row = HRResumeView(
                    id=uuid.uuid4(),
                    tenant_id=resume.tenant_id,
                    resume_id=resume.id,
                    view_type=view_type,
                    text_hash=h,
                    embedding=vec,
                    tokens=token_estimate,
                )
            else:
                row.text_hash = h
                row.embedding = vec
                row.tokens = token_estimate

            db.add(row)

        db.commit()

        _set_resume(
            db,
            resume,
            embedding_status="EMBEDDED",
            embedding_error=None,
            embedded_at=_utcnow(),
        )

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass

        resume = db.get(HRResume, resume_uuid)
        if resume is not None:
            err = f"{type(e).__name__}: {e}"
            _set_resume(db, resume, embedding_status="FAILED", embedding_error=err)
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# HR Phase 3: ScreeningRun (retrieve + rerank)
# ---------------------------------------------------------------------------


@dataclass
class _ScreeningCandidate:
    """
    In-memory candidate for a ScreeningRun.

    We keep this small and serializable so it's easy to log/debug if needed.
    """

    resume_id: UUID
    best_view_type: str
    retrieval_score: float
    rerank_score: float | None = None
    final_score_norm: float | None = None

    @property
    def final_score(self) -> float:
        # `final_score` is the UI-friendly score used for sorting and filtering.
        # We compute it as a 0..1 value and keep `rerank_score` as the raw logit.
        if self.final_score_norm is not None:
            return float(self.final_score_norm)
        return float(self.rerank_score or 0.0)


def _set_run(db: Session, run: HRScreeningRun, **fields) -> None:
    """
    Convenience helper to persist run transitions consistently.
    """
    for k, v in fields.items():
        setattr(run, k, v)
    db.add(run)
    db.commit()
    db.refresh(run)


def _normalized_screening_config(config_json: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize a ScreeningRun config dict.

    This keeps the worker logic predictable and avoids hardcoding values in the algorithm:
    - defaults come from Settings (env-driven),
    - inputs are validated and clamped.
    """
    cfg = dict(config_json or {})

    allowed_view_types = {"full", "skills", "experience"}

    raw_view_types = cfg.get("view_types") or settings.hr_screening_default_view_types
    view_types: list[str] = []
    for vt in list(raw_view_types):
        s = str(vt).strip().lower()
        if s in allowed_view_types and s not in view_types:
            view_types.append(s)

    if not view_types:
        view_types = list(settings.hr_screening_default_view_types)

    def _clamp_int(val: Any, *, default: int, min_v: int, max_v: int) -> int:
        try:
            n = int(val)
        except Exception:
            n = int(default)
        return max(min_v, min(max_v, n))

    k_per_view = _clamp_int(
        cfg.get("k_per_view"),
        default=int(settings.hr_screening_default_k_per_view),
        min_v=1,
        max_v=5000,
    )
    pool_size = _clamp_int(
        cfg.get("pool_size"),
        default=int(settings.hr_screening_default_pool_size),
        min_v=1,
        max_v=20000,
    )
    top_n = _clamp_int(
        cfg.get("top_n"),
        default=int(settings.hr_screening_default_top_n),
        min_v=1,
        max_v=5000,
    )

    # Ensure pool >= top_n so we don't generate empty results unexpectedly.
    pool_size = max(pool_size, top_n)

    return {
        "view_types": view_types,
        "k_per_view": k_per_view,
        "pool_size": pool_size,
        "top_n": top_n,
    }


def run_screening(run_id: str) -> None:
    """
    RQ job entrypoint: run a ScreeningRun for an opening.

    Pipeline:
    1) Retrieve candidates using pgvector cosine distance over resume view embeddings.
    2) Rerank the merged candidate pool using a BGE reranker (cross-encoder).
    3) Persist ranked results to `hr_screening_results`.

    Idempotency:
    - If a run is already DONE and results exist, we do nothing.
    - If a run is CANCELLED, we exit early.
    """
    run_uuid = UUID(run_id)
    db = SessionLocal()
    try:
        run = db.get(HRScreeningRun, run_uuid)
        if run is None:
            return

        # If this run is already finished, don't do anything.
        if run.status == "DONE":
            exists = (
                db.query(HRScreeningResult)
                .filter(HRScreeningResult.run_id == run.id)
                .first()
            )
            if exists is not None:
                return

        if run.status == "CANCELLED":
            return

        opening = db.get(HROpening, run.opening_id)
        if opening is None:
            _set_run(db, run, status="FAILED", error="Opening not found", finished_at=_utcnow())
            return

        # Prerequisite check: at least some embedded resumes must exist.
        embedded_count = (
            db.query(HRResumeView.resume_id)
            .join(HRResume, HRResume.id == HRResumeView.resume_id)
            .filter(
                HRResume.opening_id == opening.id,
                HRResumeView.view_type == "full",
                HRResumeView.embedding.isnot(None),
            )
            .distinct()
            .count()
        )
        if embedded_count <= 0:
            _set_run(
                db,
                run,
                status="FAILED",
                error="No embedded resumes for this opening (run embeddings first)",
                finished_at=_utcnow(),
            )
            return

        # Transition to RUNNING.
        _set_run(
            db,
            run,
            status="RUNNING",
            error=None,
            started_at=_utcnow(),
            finished_at=None,
            progress_total=0,
            progress_done=0,
        )

        # Normalize config (defaults come from Settings).
        cfg = _normalized_screening_config(run.config_json or {})
        run.config_json = cfg
        db.add(run)
        db.commit()
        db.refresh(run)

        query_text = (opening.jd_text or "").strip()
        if not query_text:
            _set_run(db, run, status="FAILED", error="Opening jd_text is empty", finished_at=_utcnow())
            return

        # Embed query once (normalized embedding => cosine distance behaves well).
        from app.hr.embeddings import embed_text

        query_emb = embed_text(query_text)

        # -----------------------------
        # Retrieval (Top-K per view type)
        # -----------------------------
        candidates_by_resume: dict[UUID, _ScreeningCandidate] = {}

        for view_type in cfg["view_types"]:
            dist_expr = HRResumeView.embedding.cosine_distance(query_emb)
            rows = (
                db.query(HRResumeView.resume_id, dist_expr.label("distance"))
                .join(HRResume, HRResume.id == HRResumeView.resume_id)
                .filter(
                    HRResume.opening_id == opening.id,
                    HRResumeView.view_type == view_type,
                    HRResumeView.embedding.isnot(None),
                )
                .order_by(dist_expr.asc())
                .limit(int(cfg["k_per_view"]))
                .all()
            )

            for resume_id, dist in rows:
                # Convert cosine distance -> similarity score for human-friendly debugging.
                dist_f = float(dist)
                retrieval_score = max(0.0, 1.0 - dist_f)

                existing = candidates_by_resume.get(resume_id)
                if existing is None or retrieval_score > existing.retrieval_score:
                    candidates_by_resume[resume_id] = _ScreeningCandidate(
                        resume_id=resume_id,
                        best_view_type=str(view_type),
                        retrieval_score=float(retrieval_score),
                    )

        merged = list(candidates_by_resume.values())
        merged.sort(key=lambda c: (-c.retrieval_score, str(c.resume_id)))

        # Trim to pool_size (this is what we rerank).
        pool = merged[: int(cfg["pool_size"])]

        _set_run(db, run, progress_total=len(pool), progress_done=0)

        # Fetch resume rows in one query to avoid N+1.
        pool_ids = [c.resume_id for c in pool]
        resume_rows = db.query(HRResume).filter(HRResume.id.in_(pool_ids)).all()
        resume_by_id = {r.id: r for r in resume_rows}

        # Build reranker docs (compact view preferred).
        from app.hr.views import build_resume_views, truncate_text

        doc_texts: list[str] = []
        for cand in pool:
            resume = resume_by_id.get(cand.resume_id)
            if resume is None:
                doc_texts.append("")
                continue

            views = build_resume_views(resume)
            compact = (views.get("skills", "") + "\n" + views.get("experience", "")).strip()
            if not compact:
                compact = views.get("full", "")

            doc_texts.append(
                truncate_text(
                    compact,
                    max_chars=int(settings.hr_reranker_max_chars),
                )
            )

        # -----------------------------
        # Rerank (cross-encoder)
        # -----------------------------
        if not settings.hr_rerank_enabled:
            _set_run(db, run, status="FAILED", error="HR reranker disabled", finished_at=_utcnow())
            return

        from app.hr.reranker import rerank_pairs

        rerank_scores: list[float] = []
        bs = max(1, int(settings.hr_reranker_batch_size))

        for i in range(0, len(doc_texts), bs):
            # Cancel check (cheap, once per batch).
            db.refresh(run)
            if run.status == "CANCELLED":
                _set_run(db, run, finished_at=_utcnow())
                return

            chunk_docs = doc_texts[i : i + bs]
            chunk_scores = rerank_pairs(query_text, chunk_docs, batch_size=bs)
            rerank_scores.extend(chunk_scores)

            done = i + len(chunk_docs)
            # Persist progress periodically so UI polling sees movement.
            if (
                done == len(doc_texts)
                or done % int(settings.hr_screening_progress_update_every) == 0
            ):
                _set_run(db, run, progress_done=done)

        # Attach rerank scores to candidates.
        # Normalize weights to keep `final_score` in a predictable 0..1 scale.
        w_ret = max(0.0, float(settings.hr_screening_score_w_retrieval))
        w_rer = max(0.0, float(settings.hr_screening_score_w_rerank))
        w_sum = w_ret + w_rer
        if w_sum <= 0.0:
            # Fallback: if misconfigured, rely only on the reranker signal.
            w_ret, w_rer, w_sum = 0.0, 1.0, 1.0
        w_ret /= w_sum
        w_rer /= w_sum

        for cand, score in zip(pool, rerank_scores):
            raw = float(score)
            cand.rerank_score = raw
            rerank01 = _sigmoid(raw)
            cand.final_score_norm = _clamp01(
                (w_ret * float(cand.retrieval_score)) + (w_rer * rerank01)
            )

        # Final ranking (MVP Phase 3: sort by rerank score, then retrieval score).
        pool.sort(
            key=lambda c: (
                -c.final_score,
                -c.retrieval_score,
                str(c.resume_id),
            )
        )

        top_n = min(int(cfg["top_n"]), len(pool))
        winners = pool[:top_n]

        # -----------------------------
        # Persist results
        # -----------------------------
        # Clear any existing rows for this run (in case the worker was restarted).
        (
            db.query(HRScreeningResult)
            .filter(HRScreeningResult.run_id == run.id)
            .delete(synchronize_session=False)
        )

        results: list[HRScreeningResult] = []
        for idx, cand in enumerate(winners, start=1):
            results.append(
                HRScreeningResult(
                    run_id=run.id,
                    resume_id=cand.resume_id,
                    tenant_id=run.tenant_id,
                    rank=idx,
                    final_score=cand.final_score,
                    rerank_score=cand.rerank_score,
                    retrieval_score=cand.retrieval_score,
                    best_view_type=cand.best_view_type,
                )
            )

        db.add_all(results)
        run.status = "DONE"
        run.finished_at = _utcnow()
        run.progress_done = int(run.progress_total)
        db.add(run)
        db.commit()

        # Phase 4: enqueue explanations for the top candidates (non-blocking).
        #
        # We do NOT block ScreeningRun completion on LLM calls. If Gemini is not
        # configured (no API key), we simply skip auto explanations.
        #
        # Manual triggers are still available via API endpoints.
        try:
            if (settings.gemini_api_key or "").strip():
                from app.hr.queue import get_hr_queue

                # Use the smaller of:
                # - the run's result size, and
                # - the configured GEMINI_MAX_TOP_N (cost/latency control)
                auto_top_n = min(int(settings.gemini_max_top_n), int(top_n))
                if auto_top_n > 0:
                    get_hr_queue().enqueue(
                        explain_run,
                        str(run.id),
                        top_n=int(auto_top_n),
                        force=False,
                        job_timeout=int(settings.hr_screening_job_timeout_sec),
                    )
        except Exception as e:
            # Explanation failures should never affect ranking; keep this best-effort.
            logger.warning(
                "failed to enqueue screening explanations",
                extra={"run_id": str(run.id), "error": str(e)},
            )

    except Exception as e:
        try:
            db.rollback()
        except Exception:
            pass

        run = db.get(HRScreeningRun, run_uuid)
        if run is not None:
            err = f"{type(e).__name__}: {e}"
            _set_run(db, run, status="FAILED", error=err, finished_at=_utcnow())
        raise
    finally:
        db.close()


# ---------------------------------------------------------------------------
# HR module (Phase 4): Explanations (Gemini, async)
# ---------------------------------------------------------------------------


def explain_run(run_id: str, top_n: int | None = None, force: bool = False) -> None:
    """
    RQ job entrypoint: generate explanations for the top N results of a ScreeningRun.

    This is intentionally separate from `run_screening`:
    - Ranking must remain fast and local (Phase 3).
    - Explanations may be slower/costly and should never block ranking completion.

    Idempotency:
    - If an explanation exists for (run_id, resume_id) with the same model + prompt version,
      we skip it unless `force=True`.
    """
    run_uuid = UUID(run_id)
    db = SessionLocal()
    try:
        run = db.get(HRScreeningRun, run_uuid)
        if run is None:
            return

        if run.status != "DONE":
            # Explanations are defined over final ranked results.
            return

        opening = db.get(HROpening, run.opening_id)
        if opening is None:
            return

        limit = int(top_n or settings.gemini_max_top_n)
        limit = max(1, min(int(settings.gemini_max_top_n), limit))

        top_results = (
            db.query(HRScreeningResult)
            .filter(HRScreeningResult.run_id == run.id)
            .order_by(HRScreeningResult.rank.asc())
            .limit(limit)
            .all()
        )

        for res in top_results:
            # Allow cancellation to stop explanation generation as well.
            db.refresh(run)
            if run.status == "CANCELLED":
                return

            _explain_one_in_db(
                db,
                run=run,
                opening=opening,
                resume_id=res.resume_id,
                rank=int(res.rank),
                force=bool(force),
            )

    finally:
        db.close()


def explain_one(run_id: str, resume_id: str, force: bool = False) -> None:
    """
    RQ job entrypoint: generate (or regenerate) one explanation for one result row.

    This is used by the API "recompute" endpoint for a single candidate.
    """
    run_uuid = UUID(run_id)
    resume_uuid = UUID(resume_id)

    db = SessionLocal()
    try:
        run = db.get(HRScreeningRun, run_uuid)
        if run is None:
            return
        if run.status != "DONE":
            return

        opening = db.get(HROpening, run.opening_id)
        if opening is None:
            return

        # Snapshot rank if present in results (optional).
        rank = (
            db.query(HRScreeningResult.rank)
            .filter(
                HRScreeningResult.run_id == run_uuid,
                HRScreeningResult.resume_id == resume_uuid,
            )
            .scalar()
        )

        _explain_one_in_db(
            db,
            run=run,
            opening=opening,
            resume_id=resume_uuid,
            rank=int(rank) if rank is not None else None,
            force=bool(force),
        )
    finally:
        db.close()


def _explain_one_in_db(
    db: Session,
    *,
    run: HRScreeningRun,
    opening: HROpening,
    resume_id: UUID,
    rank: int | None,
    force: bool,
) -> None:
    """
    Internal helper to generate and upsert one explanation row inside an existing DB session.

    We keep this separate so both `explain_run` and `explain_one` share the same logic.
    """
    from app.hr.gemini_client import generate_explanation
    from app.hr.pii import build_candidate_context
    from app.hr.prompts import PROMPT_VERSION, build_explanation_prompt

    # Resolve the resume row first (we need its local artifact paths).
    resume = db.get(HRResume, resume_id)
    if resume is None:
        return

    # Ensure we only explain parsed resumes (clean text exists).
    if resume.status != "PARSED":
        return

    model_name = settings.gemini_model

    existing = (
        db.query(HRScreeningExplanation)
        .filter(
            HRScreeningExplanation.run_id == run.id,
            HRScreeningExplanation.resume_id == resume.id,
        )
        .first()
    )
    if (
        existing is not None
        and not force
        and existing.model_name == model_name
        and existing.prompt_version == PROMPT_VERSION
    ):
        return

    candidate_context = build_candidate_context(resume)
    prompt = build_explanation_prompt(
        opening_title=opening.title,
        jd_text=opening.jd_text,
        candidate_context=candidate_context,
        language="en",
    )

    explanation = generate_explanation(prompt)

    # Upsert deterministically:
    # - We update in place if a row exists (avoid losing the old explanation if Gemini fails).
    # - We set created_at explicitly so recomputes have a fresh timestamp.
    if existing is not None:
        existing.rank = rank
        existing.model_name = model_name
        existing.prompt_version = PROMPT_VERSION
        existing.explanation_json = explanation
        existing.created_at = _utcnow()
        db.add(existing)
    else:
        row = HRScreeningExplanation(
            run_id=run.id,
            resume_id=resume.id,
            tenant_id=run.tenant_id,
            rank=rank,
            model_name=model_name,
            prompt_version=PROMPT_VERSION,
            explanation_json=explanation,
        )
        db.add(row)
    db.commit()
