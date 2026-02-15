"use client";

import { useQuery } from "@tanstack/react-query";

import type { ScreeningExplanationOut, UUID } from "@/lib/types";
import { getScreeningExplanation } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

/**
 * Fetch explanation JSON for a single (run_id, resume_id) pair.
 *
 * Notes:
 * - Backend returns 404 if not generated yet, and 409 if run isn't DONE.
 * - We keep retry disabled to avoid hammering while UI is polling run status.
 */
export function useScreeningExplanation(
  branchId: UUID | null,
  runId: UUID | null,
  resumeId: UUID | null,
  opts: { enabled?: boolean; pollIntervalMs?: number } = {}
) {
  return useQuery<ScreeningExplanationOut>({
    queryKey: hrQueryKeys.screeningExplanation(branchId, runId, resumeId),
    enabled: Boolean(opts.enabled ?? true) && Boolean(branchId && runId && resumeId),
    queryFn: ({ signal }) =>
      getScreeningExplanation(branchId as UUID, runId as UUID, resumeId as UUID, { signal }),
    refetchInterval: opts.pollIntervalMs ?? false,
    retry: false,
  });
}
