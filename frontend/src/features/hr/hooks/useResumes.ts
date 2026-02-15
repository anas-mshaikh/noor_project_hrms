"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { UUID } from "@/lib/types";
import { listResumes, uploadResumes } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

export function useResumes(branchId: UUID | null, openingId: UUID | null, statusFilter?: string) {
  const queryClient = useQueryClient();

  const list = useQuery({
    queryKey: hrQueryKeys.resumes(branchId, openingId, statusFilter),
    enabled: Boolean(branchId && openingId),
    queryFn: ({ signal }) =>
      listResumes(branchId as UUID, openingId as UUID, statusFilter, { signal }),
  });

  const upload = useMutation({
    mutationFn: (args: { files: File[] }) =>
      uploadResumes(branchId as UUID, openingId as UUID, args.files),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: hrQueryKeys.resumes(branchId, openingId) }),
  });

  return { list, upload };
}
