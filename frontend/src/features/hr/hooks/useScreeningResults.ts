"use client";

import { useQuery } from "@tanstack/react-query";

import type { ScreeningResultsPageOut, UUID } from "@/lib/types";
import { listScreeningResults } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

type Options = {
  enabled?: boolean;
  page?: number;
  pageSize?: number;
};

/**
 * Fetch paged ScreeningRun results (available only once the run is DONE).
 *
 * Backend contract:
 * - GET /api/v1/branches/{branch_id}/screening-runs/{run_id}/results?page=&page_size=
 */
export function useScreeningResults(branchId: UUID | null, runId: UUID | null, opts?: Options) {
  const enabled = Boolean(opts?.enabled ?? true);
  const page = opts?.page ?? 1;
  const pageSize = opts?.pageSize ?? 50;

  return useQuery<ScreeningResultsPageOut>({
    queryKey: hrQueryKeys.screeningResults(branchId, runId, page, pageSize),
    enabled: enabled && Boolean(branchId && runId),
    queryFn: ({ signal }) =>
      listScreeningResults(branchId as UUID, runId as UUID, { page, pageSize }, { signal }),
    retry: false, // backend returns 409 until DONE; don't spam.
  });
}
