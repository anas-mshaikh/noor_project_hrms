import type { IamRoleAssignIn, UUID } from "@/lib/types";

export type RoleScopeKind = "TENANT" | "COMPANY" | "BRANCH";

export function validateRoleAssignmentInput(args: {
  roleCode: string;
  scopeKind: RoleScopeKind;
  companyId?: UUID | null;
  branchId?: UUID | null;
}): string | null {
  if (!args.roleCode.trim()) return "Role is required.";
  if (args.scopeKind === "TENANT") return null;
  if (args.scopeKind === "COMPANY") {
    if (!args.companyId) return "Company is required.";
    return null;
  }
  if (args.scopeKind === "BRANCH") {
    if (!args.companyId) return "Company is required.";
    if (!args.branchId) return "Branch is required.";
    return null;
  }
  return "Invalid scope.";
}

export function buildRoleAssignIn(args: {
  roleCode: string;
  scopeKind: RoleScopeKind;
  companyId?: UUID | null;
  branchId?: UUID | null;
}): IamRoleAssignIn {
  if (args.scopeKind === "TENANT") {
    return { role_code: args.roleCode };
  }
  if (args.scopeKind === "COMPANY") {
    return { role_code: args.roleCode, company_id: args.companyId ?? null, branch_id: null };
  }
  return {
    role_code: args.roleCode,
    company_id: args.companyId ?? null,
    branch_id: args.branchId ?? null,
  };
}

