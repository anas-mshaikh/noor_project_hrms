import { apiJson } from "@/lib/api";
import type {
  EmployeeDirectoryListOut,
  HrEmployee360Out,
  HrEmployeeCreateIn,
  HrEmployeeLinkUserIn,
  HrEmployeeUserLinkOut,
  HrEmploymentChangeIn,
  HrEmploymentOut,
  UUID,
} from "@/lib/types";

/**
 * HR Core API wrapper (canonical employee master).
 *
 * Notes:
 * - Pure functions only (no React).
 * - Company scope is typically inferred from the active scope headers; we also
 *   support explicit `company_id` query param for tests or special cases.
 */

export async function listEmployees(
  args: {
    companyId?: UUID | null;
    q?: string | null;
    status?: string | null;
    branchId?: UUID | null;
    orgUnitId?: UUID | null;
    limit: number;
    offset: number;
  },
  init?: RequestInit
): Promise<EmployeeDirectoryListOut> {
  const qs = new URLSearchParams({
    limit: String(args.limit),
    offset: String(args.offset),
  });
  if (args.companyId) qs.set("company_id", args.companyId);
  if (args.q) qs.set("q", args.q);
  if (args.status) qs.set("status", args.status);
  if (args.branchId) qs.set("branch_id", args.branchId);
  if (args.orgUnitId) qs.set("org_unit_id", args.orgUnitId);

  return apiJson<EmployeeDirectoryListOut>(`/api/v1/hr/employees?${qs.toString()}`, init);
}

export async function createEmployee(
  payload: HrEmployeeCreateIn,
  init?: RequestInit
): Promise<HrEmployee360Out> {
  return apiJson<HrEmployee360Out>("/api/v1/hr/employees", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function getEmployee(
  args: { employeeId: UUID; companyId?: UUID | null },
  init?: RequestInit
): Promise<HrEmployee360Out> {
  const qs = args.companyId ? `?company_id=${encodeURIComponent(args.companyId)}` : "";
  return apiJson<HrEmployee360Out>(`/api/v1/hr/employees/${args.employeeId}${qs}`, init);
}

export async function listEmploymentHistory(
  args: { employeeId: UUID; companyId?: UUID | null },
  init?: RequestInit
): Promise<HrEmploymentOut[]> {
  const qs = args.companyId ? `?company_id=${encodeURIComponent(args.companyId)}` : "";
  return apiJson<HrEmploymentOut[]>(`/api/v1/hr/employees/${args.employeeId}/employment${qs}`, init);
}

export async function changeEmployment(
  args: { employeeId: UUID; payload: HrEmploymentChangeIn; companyId?: UUID | null },
  init?: RequestInit
): Promise<HrEmployee360Out> {
  const qs = args.companyId ? `?company_id=${encodeURIComponent(args.companyId)}` : "";
  return apiJson<HrEmployee360Out>(`/api/v1/hr/employees/${args.employeeId}/employment${qs}`, {
    method: "POST",
    body: JSON.stringify(args.payload),
    ...init,
  });
}

export async function linkEmployeeUser(
  args: { employeeId: UUID; payload: HrEmployeeLinkUserIn; companyId?: UUID | null },
  init?: RequestInit
): Promise<HrEmployeeUserLinkOut> {
  const qs = args.companyId ? `?company_id=${encodeURIComponent(args.companyId)}` : "";
  return apiJson<HrEmployeeUserLinkOut>(`/api/v1/hr/employees/${args.employeeId}/link-user${qs}`, {
    method: "POST",
    body: JSON.stringify(args.payload),
    ...init,
  });
}

