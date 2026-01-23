"use client";

import { useQuery } from "@tanstack/react-query";

import type { UUID } from "@/lib/types";
import { getParsedResume } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

/**
 * Fetch parsed resume artifact (only when drawer is open).
 * Backend returns 409 if resume isn't parsed yet.
 */
export function useParsedResume(resumeId: UUID | null, enabled: boolean) {
  return useQuery({
    queryKey: hrQueryKeys.parsedResume(resumeId),
    enabled: enabled && Boolean(resumeId),
    queryFn: ({ signal }) => getParsedResume(resumeId as UUID, { signal }),
    retry: false, // don't spam 409s
  });
}

