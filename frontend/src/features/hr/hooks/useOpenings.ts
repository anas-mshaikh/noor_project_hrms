"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { OpeningCreateRequest, OpeningUpdateRequest, UUID } from "@/lib/types";
import { createOpening, listOpenings, updateOpening } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

/**
 * Openings list + mutations (branch-scoped).
 *
 * We keep hooks thin:
 * - all request details live in `features/hr/api/hr.ts`
 * - all cache keys live in `features/hr/api/queryKeys.ts`
 */
export function useOpenings(branchId: UUID | null) {
  const queryClient = useQueryClient();

  const list = useQuery({
    queryKey: hrQueryKeys.openings(branchId),
    enabled: Boolean(branchId),
    queryFn: ({ signal }) => listOpenings(branchId as UUID, { signal }),
  });

  const create = useMutation({
    mutationFn: (payload: OpeningCreateRequest) =>
      createOpening(branchId as UUID, payload),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: hrQueryKeys.openings(branchId) }),
  });

  const patch = useMutation({
    mutationFn: (args: { openingId: UUID; payload: OpeningUpdateRequest }) =>
      updateOpening(branchId as UUID, args.openingId, args.payload),
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: hrQueryKeys.openings(branchId) });
      queryClient.setQueryData(
        hrQueryKeys.opening(branchId, updated.id),
        updated
      );
    },
  });

  return { list, create, patch };
}
