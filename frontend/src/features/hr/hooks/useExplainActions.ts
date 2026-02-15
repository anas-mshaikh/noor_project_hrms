"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import type { UUID } from "@/lib/types";
import {
  enqueueRunExplanations,
  recomputeSingleExplanation,
} from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

/**
 * Mutations for Phase 4 explanation generation (Gemini).
 *
 * These endpoints enqueue RQ jobs; they do NOT block.
 */
export function useExplainActions(branchId: UUID | null, runId: UUID | null) {
  const queryClient = useQueryClient();

  const enqueue = useMutation({
    mutationFn: (args?: { topN?: number; force?: boolean }) =>
      enqueueRunExplanations(branchId as UUID, runId as UUID, args),
    onSuccess: () => {
      // Explanations are fetched per-resume; invalidate broadly for this run.
      queryClient.invalidateQueries({
        queryKey: ["hr", "screening-explanation", branchId, runId],
      });
    },
  });

  const recomputeOne = useMutation({
    mutationFn: (args: { resumeId: UUID; force?: boolean }) =>
      recomputeSingleExplanation(branchId as UUID, runId as UUID, args.resumeId, {
        force: args.force,
      }),
    onSuccess: (_resp, vars) => {
      queryClient.invalidateQueries({
        queryKey: hrQueryKeys.screeningExplanation(branchId, runId, vars.resumeId),
      });
    },
  });

  return { enqueue, recomputeOne };
}
