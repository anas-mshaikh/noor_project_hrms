"use client";

/**
 * HR scoring helpers (frontend).
 *
 * Backend contract (Phase 3+):
 * - `rerank_score` can be a raw, unbounded logit (often negative).
 * - `final_score` should be normalized to 0..1 (sigmoid(logit)) for UI filters.
 *
 * For safety/backwards compatibility, we still handle:
 * - `final_score` already being 0..100 percent
 * - `final_score` accidentally being a raw logit (older runs) -> we sigmoid it
 */

export function sigmoid(x: number): number {
  if (!Number.isFinite(x)) return 0.0;
  if (x >= 0) {
    const z = Math.exp(-x);
    return 1.0 / (1.0 + z);
  }
  const z = Math.exp(x);
  return z / (1.0 + z);
}

export function toScore01(score: number): number {
  if (!Number.isFinite(score)) return 0.0;

  // Already normalized.
  if (score >= 0 && score <= 1) return score;

  // Already a percent.
  if (score >= 0 && score <= 100) return score / 100.0;

  // Older runs might have stored raw logits in `final_score`.
  return sigmoid(score);
}

export function toScorePercent(score: number): number {
  const s01 = toScore01(score);
  const pct = Math.round(s01 * 100);
  return Math.max(0, Math.min(100, pct));
}
