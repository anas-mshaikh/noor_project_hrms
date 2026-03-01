import { describe, expect, it } from "vitest";

import { buildRoleAssignIn, validateRoleAssignmentInput } from "./roleAssignment";

describe("features/iam/roleAssignment", () => {
  it("validates required fields for branch scope", () => {
    expect(
      validateRoleAssignmentInput({
        roleCode: "HR_ADMIN",
        scopeKind: "BRANCH",
        companyId: null,
        branchId: null,
      })
    ).toBe("Company is required.");
    expect(
      validateRoleAssignmentInput({
        roleCode: "HR_ADMIN",
        scopeKind: "BRANCH",
        companyId: "c1",
        branchId: null,
      })
    ).toBe("Branch is required.");
    expect(
      validateRoleAssignmentInput({
        roleCode: "HR_ADMIN",
        scopeKind: "BRANCH",
        companyId: "c1",
        branchId: "b1",
      })
    ).toBeNull();
  });

  it("builds RoleAssignIn deterministically", () => {
    expect(
      buildRoleAssignIn({ roleCode: "ADMIN", scopeKind: "TENANT" })
    ).toEqual({ role_code: "ADMIN" });
    expect(
      buildRoleAssignIn({ roleCode: "ADMIN", scopeKind: "COMPANY", companyId: "c1" })
    ).toEqual({ role_code: "ADMIN", company_id: "c1", branch_id: null });
    expect(
      buildRoleAssignIn({ roleCode: "ADMIN", scopeKind: "BRANCH", companyId: "c1", branchId: "b1" })
    ).toEqual({ role_code: "ADMIN", company_id: "c1", branch_id: "b1" });
  });
});

