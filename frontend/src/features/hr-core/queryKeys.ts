import type { UUID } from "@/lib/types";

export const hrCoreKeys = {
  employees: (args: {
    companyId: UUID | null;
    q?: string | null;
    status?: string | null;
    branchId?: UUID | null;
    orgUnitId?: UUID | null;
    limit: number;
    offset: number;
  }) =>
    [
      "hr-core",
      "employees",
      args.companyId,
      args.q ?? null,
      args.status ?? null,
      args.branchId ?? null,
      args.orgUnitId ?? null,
      args.limit,
      args.offset,
    ] as const,
  employee: (args: { companyId: UUID | null; employeeId: UUID | null }) =>
    ["hr-core", "employee", args.companyId, args.employeeId] as const,
  employmentHistory: (args: { companyId: UUID | null; employeeId: UUID | null }) =>
    ["hr-core", "employment-history", args.companyId, args.employeeId] as const,
};

