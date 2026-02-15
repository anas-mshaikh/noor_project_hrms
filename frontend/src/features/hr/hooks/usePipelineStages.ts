"use client";

import { useQuery } from "@tanstack/react-query";

import type { PipelineStageOut, UUID } from "@/lib/types";
import { listPipelineStages } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

/**
 * Fetch pipeline stages for an opening (ATS).
 *
 * Backend:
 * - GET /api/v1/branches/{branch_id}/openings/{opening_id}/pipeline-stages
 */
export function usePipelineStages(branchId: UUID | null, openingId: UUID | null) {
  return useQuery<PipelineStageOut[]>({
    queryKey: hrQueryKeys.pipelineStages(branchId, openingId),
    enabled: Boolean(branchId && openingId),
    queryFn: ({ signal }) =>
      listPipelineStages(branchId as UUID, openingId as UUID, { signal }),
  });
}
