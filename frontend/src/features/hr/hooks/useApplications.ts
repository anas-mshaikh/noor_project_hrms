"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { ApplicationOut, ApplicationUpdateRequest, UUID } from "@/lib/types";
import {
  hireApplication,
  listApplications,
  rejectApplication,
  updateApplication,
} from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

type MoveArgs = { applicationId: UUID; stageId: UUID };

/**
 * Fetch applications for an opening and provide mutations for common actions.
 *
 * Backend:
 * - GET   /api/v1/branches/{branch_id}/openings/{opening_id}/applications
 * - PATCH /api/v1/branches/{branch_id}/applications/{application_id}
 * - POST  /api/v1/branches/{branch_id}/applications/{application_id}/reject
 * - POST  /api/v1/branches/{branch_id}/applications/{application_id}/hire
 */
export function useApplications(branchId: UUID | null, openingId: UUID | null) {
  const queryClient = useQueryClient();
  const key = hrQueryKeys.applications(branchId, openingId);

  const list = useQuery<ApplicationOut[]>({
    queryKey: key,
    enabled: Boolean(branchId && openingId),
    queryFn: ({ signal }) =>
      listApplications(branchId as UUID, openingId as UUID, undefined, { signal }),
  });

  const moveStage = useMutation({
    mutationFn: async (args: MoveArgs) => {
      const payload: ApplicationUpdateRequest = { stage_id: args.stageId };
      return updateApplication(branchId as UUID, args.applicationId, payload);
    },
    onMutate: async (args) => {
      await queryClient.cancelQueries({ queryKey: key });
      const previous = queryClient.getQueryData<ApplicationOut[]>(key);

      if (previous) {
        queryClient.setQueryData<ApplicationOut[]>(
          key,
          previous.map((a) =>
            a.id === args.applicationId
              ? { ...a, stage_id: args.stageId, updated_at: new Date().toISOString() }
              : a
          )
        );
      }

      return { previous };
    },
    onSuccess: (updated) => {
      const current = queryClient.getQueryData<ApplicationOut[]>(key);
      if (!current) return;
      queryClient.setQueryData<ApplicationOut[]>(
        key,
        current.map((a) => (a.id === updated.id ? updated : a))
      );
    },
    onError: (_err, _args, ctx) => {
      if (ctx?.previous) queryClient.setQueryData(key, ctx.previous);
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const reject = useMutation({
    mutationFn: (applicationId: UUID) => rejectApplication(branchId as UUID, applicationId),
    onSuccess: (updated) => {
      const current = queryClient.getQueryData<ApplicationOut[]>(key);
      if (!current) return;
      queryClient.setQueryData<ApplicationOut[]>(
        key,
        current.map((a) => (a.id === updated.id ? updated : a))
      );
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  const hire = useMutation({
    mutationFn: (applicationId: UUID) => hireApplication(branchId as UUID, applicationId),
    onSuccess: (updated) => {
      const current = queryClient.getQueryData<ApplicationOut[]>(key);
      if (!current) return;
      queryClient.setQueryData<ApplicationOut[]>(
        key,
        current.map((a) => (a.id === updated.id ? updated : a))
      );
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  return { list, moveStage, reject, hire };
}
