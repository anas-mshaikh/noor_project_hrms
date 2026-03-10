import type { UUID } from "@/lib/types";

export const payablesKeys = {
  me: (args: { from: string; to: string }) =>
    ["payables", "me", args.from, args.to] as const,
  team: (args: { from: string; to: string; depth: "1" | "all" }) =>
    ["payables", "team", args.from, args.to, args.depth] as const,
  admin: (args: {
    from: string;
    to: string;
    branchId: UUID | null;
    employeeId: UUID | null;
    limit: number;
  }) =>
    [
      "payables",
      "admin",
      args.from,
      args.to,
      args.branchId,
      args.employeeId,
      args.limit,
    ] as const,
};
