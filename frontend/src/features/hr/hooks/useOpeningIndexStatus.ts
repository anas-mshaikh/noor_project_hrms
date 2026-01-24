"use client";

import { useQuery } from "@tanstack/react-query";

import type { OpeningIndexStatusOut, UUID } from "@/lib/types";
import { getOpeningIndexStatus } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

function shouldPoll(d: OpeningIndexStatusOut | undefined): boolean {
  if (!d) return true;
  // Poll while we have parsed resumes that are not fully embedded yet.
  if (d.parsed_resumes <= 0) return false;
  return d.embedded_resumes + d.embedding_failed < d.parsed_resumes;
}

/**
 * Phase 2: opening-level index/embedding status.
 *
 * Backend contract:
 * - GET /api/v1/openings/{opening_id}/resumes/index-status
 */
export function useOpeningIndexStatus(openingId: UUID | null) {
  return useQuery<OpeningIndexStatusOut>({
    queryKey: hrQueryKeys.openingIndexStatus(openingId),
    enabled: Boolean(openingId),
    queryFn: ({ signal }) => getOpeningIndexStatus(openingId as UUID, { signal }),
    refetchInterval: (q) => (shouldPoll(q.state.data) ? 1500 : false),
  });
}

