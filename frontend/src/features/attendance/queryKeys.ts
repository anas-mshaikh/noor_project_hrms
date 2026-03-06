/**
 * Attendance query keys (React Query).
 *
 * Cursor pagination: cursor must NOT be part of the query key; it is passed
 * via `pageParam` in `useInfiniteQuery`.
 */
export const attendanceKeys = {
  punchState: () => ["attendance", "punch-state"] as const,

  days: (args: { from: string; to: string }) =>
    ["attendance", "days", args.from, args.to] as const,

  myCorrections: (args: { status?: string | null; limit: number }) =>
    ["attendance", "my-corrections", args.status ?? null, args.limit] as const,
};

