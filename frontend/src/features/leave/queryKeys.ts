import type { UUID } from "@/lib/types";

/**
 * Leave query keys (React Query).
 *
 * Cursor pagination: cursor must NOT be part of the query key; it is passed
 * via `pageParam` in `useInfiniteQuery`.
 */
export const leaveKeys = {
  balances: (year: number) => ["leave", "balances", year] as const,

  myRequests: (args: { status?: string | null; limit: number }) =>
    ["leave", "my-requests", args.status ?? null, args.limit] as const,

  teamCalendar: (args: {
    from: string;
    to: string;
    depth: string;
    branchId?: UUID | null;
  }) =>
    [
      "leave",
      "team-calendar",
      args.from,
      args.to,
      args.depth,
      args.branchId ?? null,
    ] as const,
};
