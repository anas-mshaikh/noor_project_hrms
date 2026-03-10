import type { UUID } from "@/lib/types";

export const rosterKeys = {
  shifts: (args: { branchId: UUID | null; activeOnly: boolean }) =>
    ["roster", "shifts", args.branchId, args.activeOnly] as const,
  defaultShift: (branchId: UUID | null) =>
    ["roster", "default-shift", branchId] as const,
  assignments: (employeeId: UUID | null) =>
    ["roster", "assignments", employeeId] as const,
  overrides: (args: { employeeId: UUID | null; from: string; to: string }) =>
    ["roster", "overrides", args.employeeId, args.from, args.to] as const,
};
