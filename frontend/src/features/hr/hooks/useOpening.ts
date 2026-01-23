"use client";

import { useQuery } from "@tanstack/react-query";

import type { UUID } from "@/lib/types";
import { getOpening } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

export function useOpening(openingId: UUID | null) {
  return useQuery({
    queryKey: hrQueryKeys.opening(openingId),
    enabled: Boolean(openingId),
    queryFn: ({ signal }) => getOpening(openingId as UUID, { signal }),
  });
}

