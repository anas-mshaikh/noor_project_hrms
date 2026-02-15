"use client";

import * as React from "react";
import { useQuery } from "@tanstack/react-query";

import type { UUID } from "@/lib/types";
import { getBatchStatus } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

type BatchPollInput =
  | { branchId: UUID; openingId: UUID; batchId: UUID; enabled?: boolean }
  | null;

function isDone(s: {
  parsed_count: number;
  failed_count: number;
  total_count: number;
}): boolean {
  return s.parsed_count + s.failed_count >= s.total_count;
}

/**
 * Polls batch status while parsing is in-flight.
 * Stops automatically when parsed+failed == total.
 */
export function useBatchPoll(input: BatchPollInput) {
  const [done, setDone] = React.useState(false);

  const branchId = input?.branchId ?? null;
  const openingId = input?.openingId ?? null;
  const batchId = input?.batchId ?? null;
  const enabled = Boolean(input?.enabled ?? true);

  const query = useQuery({
    queryKey: hrQueryKeys.batchStatus(branchId, openingId, batchId),
    enabled: enabled && Boolean(branchId) && Boolean(openingId) && Boolean(batchId) && !done,
    queryFn: ({ signal }) =>
      getBatchStatus(branchId as UUID, openingId as UUID, batchId as UUID, { signal }),
    refetchInterval: (q) => {
      const data = q.state.data;
      if (!data) return 1200;
      return isDone(data) ? false : 1200;
    },
  });

  React.useEffect(() => {
    if (query.data && isDone(query.data)) setDone(true);
  }, [query.data]);

  return {
    ...query,
    done,
    isPolling: enabled && !done && query.fetchStatus === "fetching",
    resetDone: () => setDone(false),
  };
}
