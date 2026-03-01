import type { UUID } from "@/lib/types";

export const tenancyKeys = {
  companies: () => ["tenancy", "companies"] as const,
  branches: (companyId?: UUID | null) =>
    ["tenancy", "branches", companyId ?? null] as const,
  orgUnits: (args: { companyId: UUID; branchId?: UUID | null }) =>
    ["tenancy", "org-units", args.companyId, args.branchId ?? null] as const,
  orgChart: (args: { companyId: UUID; branchId?: UUID | null }) =>
    ["tenancy", "org-chart", args.companyId, args.branchId ?? null] as const,
  jobTitles: (companyId: UUID) => ["tenancy", "job-titles", companyId] as const,
  grades: (companyId: UUID) => ["tenancy", "grades", companyId] as const,
};

