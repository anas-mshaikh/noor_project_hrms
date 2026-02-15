"use client";

import { useQuery } from "@tanstack/react-query";

import type { UUID } from "@/lib/types";
import { getOpening } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

export function useOpening(branchId: UUID | null, openingId: UUID | null) {
  return useQuery({
    queryKey: hrQueryKeys.opening(branchId, openingId),
    enabled: Boolean(branchId && openingId),
    queryFn: ({ signal }) =>
      getOpening(branchId as UUID, openingId as UUID, { signal }),
  });
}
