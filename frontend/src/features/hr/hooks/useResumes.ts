"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { UUID } from "@/lib/types";
import { listResumes, uploadResumes } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

export function useResumes(openingId: UUID | null, statusFilter?: string) {
  const queryClient = useQueryClient();

  const list = useQuery({
    queryKey: hrQueryKeys.resumes(openingId, statusFilter),
    enabled: Boolean(openingId),
    queryFn: ({ signal }) =>
      listResumes(openingId as UUID, statusFilter, { signal }),
  });

  const upload = useMutation({
    mutationFn: (args: { files: File[] }) =>
      uploadResumes(openingId as UUID, args.files),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: hrQueryKeys.resumes(openingId) }),
  });

  return { list, upload };
}

