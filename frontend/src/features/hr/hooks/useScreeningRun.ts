"use client";

import { useQuery } from "@tanstack/react-query";

import type { UUID } from "@/lib/types";
import { getScreeningRun } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

function shouldPoll(status: string | undefined): boolean {
  return status === "QUEUED" || status === "RUNNING";
}

function getPollIntervalMs(status: string | undefined, progressTotal: number | null | undefined): number | false {
  if (!shouldPoll(status)) return false;

  // Reduce spam while the worker is in its "startup" phase (model load / downloads),
  // where `progress_total` is still 0 and the UI can't show meaningful progress yet.
  if (status === "RUNNING" && (progressTotal ?? 0) === 0) return 5000;

  // Normal cadence for interactive status updates.
  return 1500;
}

/**
 * Poll ScreeningRun status while it's in-flight (QUEUED/RUNNING).
 *
 * Backend contract:
 * - GET /api/v1/screening-runs/{run_id}
 */
export function useScreeningRun(runId: UUID | null) {
  return useQuery({
    queryKey: hrQueryKeys.screeningRun(runId),
    enabled: Boolean(runId),
    queryFn: ({ signal }) => getScreeningRun(runId as UUID, { signal }),
    refetchInterval: (q) => {
      const status = q.state.data?.status;
      const progressTotal = q.state.data?.progress_total ?? null;
      return getPollIntervalMs(status, progressTotal);
    },
  });
}
