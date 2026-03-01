/**
 * test/utils/requests.ts
 *
 * Helpers to assert request invariants inside MSW handlers.
 */

export function expectScopeHeaders(
  request: Request,
  expected: {
    tenantId?: string | null;
    companyId?: string | null;
    branchId?: string | null;
  }
): void {
  const hTenant = request.headers.get("x-tenant-id");
  const hCompany = request.headers.get("x-company-id");
  const hBranch = request.headers.get("x-branch-id");

  if (expected.tenantId !== undefined && String(expected.tenantId ?? "") !== String(hTenant ?? "")) {
    throw new Error(`Expected X-Tenant-Id=${expected.tenantId} but got ${hTenant}`);
  }
  if (expected.companyId !== undefined && String(expected.companyId ?? "") !== String(hCompany ?? "")) {
    throw new Error(`Expected X-Company-Id=${expected.companyId} but got ${hCompany}`);
  }
  if (expected.branchId !== undefined && String(expected.branchId ?? "") !== String(hBranch ?? "")) {
    throw new Error(`Expected X-Branch-Id=${expected.branchId} but got ${hBranch}`);
  }
}

