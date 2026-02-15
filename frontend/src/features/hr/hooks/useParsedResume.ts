"use client";

import { useQuery } from "@tanstack/react-query";

import type { UUID } from "@/lib/types";
import { getParsedResume } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

/**
 * Fetch parsed resume artifact (only when drawer is open).
 * Backend returns 409 if resume isn't parsed yet.
 */
export function useParsedResume(branchId: UUID | null, resumeId: UUID | null, enabled: boolean) {
  return useQuery({
    queryKey: hrQueryKeys.parsedResume(branchId, resumeId),
    enabled: enabled && Boolean(branchId && resumeId),
    queryFn: ({ signal }) =>
      getParsedResume(branchId as UUID, resumeId as UUID, { signal }),
    retry: false, // don't spam 409s
  });
}
