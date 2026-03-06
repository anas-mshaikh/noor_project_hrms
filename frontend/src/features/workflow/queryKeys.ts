import type { UUID } from "@/lib/types";

/**
 * Workflow query keys (React Query).
 *
 * Cursor pagination: cursor must NOT be part of the query key; it is passed
 * via `pageParam` in `useInfiniteQuery`.
 */
export const workflowKeys = {
  inbox: (args: {
    status: "pending" | "submitted" | string;
    type?: string | null;
    companyId?: UUID | null;
    branchId?: UUID | null;
    limit: number;
  }) =>
    [
      "workflow",
      "inbox",
      args.status,
      args.type ?? null,
      args.companyId ?? null,
      args.branchId ?? null,
      args.limit,
    ] as const,

  outbox: (args: { status?: string | null; type?: string | null; limit: number }) =>
    ["workflow", "outbox", args.status ?? null, args.type ?? null, args.limit] as const,

  request: (requestId: UUID | null) => ["workflow", "request", requestId] as const,

  definitions: (companyId: UUID | null) => ["workflow", "definitions", companyId] as const,
};

