"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import type { NoteOut, UUID } from "@/lib/types";
import { createApplicationNote, listApplicationNotes } from "@/features/hr/api/hr";
import { hrQueryKeys } from "@/features/hr/api/queryKeys";

/**
 * Notes for an ATS application.
 *
 * Backend:
 * - GET  /api/v1/applications/{application_id}/notes
 * - POST /api/v1/applications/{application_id}/notes
 */
export function useApplicationNotes(applicationId: UUID | null) {
  const queryClient = useQueryClient();
  const key = hrQueryKeys.applicationNotes(applicationId);

  const list = useQuery<NoteOut[]>({
    queryKey: key,
    enabled: Boolean(applicationId),
    queryFn: ({ signal }) =>
      listApplicationNotes(applicationId as UUID, { signal }),
  });

  const create = useMutation({
    mutationFn: (args: { note: string }) =>
      createApplicationNote(applicationId as UUID, { note: args.note }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: key }),
  });

  return { list, create };
}

