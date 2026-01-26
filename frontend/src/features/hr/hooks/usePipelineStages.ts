"use client";

import { useQuery } from "@tanstack/react-query";

import type { PipelineStageOut, UUID } from "@/lib/types";
import { listPipelineStages } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

/**
 * Fetch pipeline stages for an opening (ATS).
 *
 * Backend:
 * - GET /api/v1/openings/{opening_id}/pipeline-stages
 */
export function usePipelineStages(openingId: UUID | null) {
  return useQuery<PipelineStageOut[]>({
    queryKey: hrQueryKeys.pipelineStages(openingId),
    enabled: Boolean(openingId),
    queryFn: ({ signal }) => listPipelineStages(openingId as UUID, { signal }),
  });
}

