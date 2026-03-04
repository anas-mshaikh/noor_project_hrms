import type { UUID } from "@/lib/types";

export const mssKeys = {
  team: (args: {
    depth: string;
    q?: string | null;
    status?: string | null;
    branchId?: UUID | null;
    orgUnitId?: UUID | null;
    limit: number;
    offset: number;
  }) =>
    [
      "mss",
      "team",
      args.depth,
      args.q ?? null,
      args.status ?? null,
      args.branchId ?? null,
      args.orgUnitId ?? null,
      args.limit,
      args.offset,
    ] as const,
  member: (employeeId: UUID | null) => ["mss", "team-member", employeeId] as const,
};

