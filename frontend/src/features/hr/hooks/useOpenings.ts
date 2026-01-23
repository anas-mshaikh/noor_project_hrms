"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { OpeningCreateRequest, OpeningUpdateRequest, UUID } from "@/lib/types";
import { createOpening, listOpenings, updateOpening } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

/**
 * Openings list + mutations (store-scoped).
 *
 * We keep hooks thin:
 * - all request details live in `features/hr/api/hr.ts`
 * - all cache keys live in `features/hr/api/queryKeys.ts`
 */
export function useOpenings(storeId: UUID | null) {
  const queryClient = useQueryClient();

  const list = useQuery({
    queryKey: hrQueryKeys.openings(storeId),
    enabled: Boolean(storeId),
    queryFn: ({ signal }) => listOpenings(storeId as UUID, { signal }),
  });

  const create = useMutation({
    mutationFn: (payload: OpeningCreateRequest) =>
      createOpening(storeId as UUID, payload),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: hrQueryKeys.openings(storeId) }),
  });

  const patch = useMutation({
    mutationFn: (args: { openingId: UUID; payload: OpeningUpdateRequest }) =>
      updateOpening(args.openingId, args.payload),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: hrQueryKeys.openings(storeId) });
      queryClient.setQueryData(hrQueryKeys.opening(updated.id), updated);
    },
  });

  return { list, create, patch };
}

