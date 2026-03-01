import { apiJson } from "@/lib/api";
import type {
  BranchCreate,
  BranchOut,
  CompanyCreate,
  CompanyOut,
  GradeCreate,
  GradeOut,
  JobTitleCreate,
  JobTitleOut,
  OrgUnitCreate,
  OrgUnitNode,
  OrgUnitOut,
  UUID,
} from "@/lib/types";

/**
 * Tenancy API wrapper (vNext masters).
 *
 * Notes:
 * - Pure functions only (no React). Hooks/pages call these.
 * - All requests go through `lib/api.ts` for scope/error normalization.
 */

export async function listCompanies(init?: RequestInit): Promise<CompanyOut[]> {
  return apiJson<CompanyOut[]>("/api/v1/tenancy/companies", init);
}

export async function createCompany(
  payload: CompanyCreate,
  init?: RequestInit
): Promise<CompanyOut> {
  return apiJson<CompanyOut>("/api/v1/tenancy/companies", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function listBranches(
  args?: { companyId?: UUID | null },
  init?: RequestInit
): Promise<BranchOut[]> {
  const qs = args?.companyId ? `?company_id=${encodeURIComponent(args.companyId)}` : "";
  return apiJson<BranchOut[]>(`/api/v1/tenancy/branches${qs}`, init);
}

export async function createBranch(
  payload: BranchCreate,
  init?: RequestInit
): Promise<BranchOut> {
  return apiJson<BranchOut>("/api/v1/tenancy/branches", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function listOrgUnits(
  args: { companyId: UUID; branchId?: UUID | null },
  init?: RequestInit
): Promise<OrgUnitOut[]> {
  const qs = new URLSearchParams({ company_id: args.companyId });
  if (args.branchId) qs.set("branch_id", args.branchId);
  return apiJson<OrgUnitOut[]>(`/api/v1/tenancy/org-units?${qs.toString()}`, init);
}

export async function createOrgUnit(
  payload: OrgUnitCreate,
  init?: RequestInit
): Promise<OrgUnitOut> {
  return apiJson<OrgUnitOut>("/api/v1/tenancy/org-units", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function getOrgChart(
  args: { companyId: UUID; branchId?: UUID | null },
  init?: RequestInit
): Promise<OrgUnitNode[]> {
  const qs = new URLSearchParams({ company_id: args.companyId });
  if (args.branchId) qs.set("branch_id", args.branchId);
  return apiJson<OrgUnitNode[]>(`/api/v1/tenancy/org-chart?${qs.toString()}`, init);
}

export async function listJobTitles(
  args: { companyId: UUID },
  init?: RequestInit
): Promise<JobTitleOut[]> {
  const qs = new URLSearchParams({ company_id: args.companyId });
  return apiJson<JobTitleOut[]>(`/api/v1/tenancy/job-titles?${qs.toString()}`, init);
}

export async function createJobTitle(
  payload: JobTitleCreate,
  init?: RequestInit
): Promise<JobTitleOut> {
  return apiJson<JobTitleOut>("/api/v1/tenancy/job-titles", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function listGrades(
  args: { companyId: UUID },
  init?: RequestInit
): Promise<GradeOut[]> {
  const qs = new URLSearchParams({ company_id: args.companyId });
  return apiJson<GradeOut[]>(`/api/v1/tenancy/grades?${qs.toString()}`, init);
}

export async function createGrade(
  payload: GradeCreate,
  init?: RequestInit
): Promise<GradeOut> {
  return apiJson<GradeOut>("/api/v1/tenancy/grades", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

