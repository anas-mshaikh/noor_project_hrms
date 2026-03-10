import { apiJson } from "@/lib/api";
import type {
  BranchDefaultShiftOut,
  BranchDefaultShiftUpsertIn,
  RosterOverrideOut,
  RosterOverrideUpsertIn,
  ShiftAssignmentCreateIn,
  ShiftAssignmentOut,
  ShiftTemplateCreateIn,
  ShiftTemplateOut,
  ShiftTemplatePatchIn,
  UUID,
} from "@/lib/types";

export async function listShiftTemplates(
  args: { branchId: UUID; activeOnly?: boolean },
  init?: RequestInit,
): Promise<ShiftTemplateOut[]> {
  const qs = new URLSearchParams({
    active_only: String(args.activeOnly ?? true),
  });
  return apiJson<ShiftTemplateOut[]>(
    `/api/v1/roster/branches/${args.branchId}/shifts?${qs.toString()}`,
    init,
  );
}

export async function createShiftTemplate(
  branchId: UUID,
  payload: ShiftTemplateCreateIn,
  init?: RequestInit,
): Promise<ShiftTemplateOut> {
  return apiJson<ShiftTemplateOut>(`/api/v1/roster/branches/${branchId}/shifts`, {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function patchShiftTemplate(
  shiftTemplateId: UUID,
  payload: ShiftTemplatePatchIn,
  init?: RequestInit,
): Promise<ShiftTemplateOut> {
  return apiJson<ShiftTemplateOut>(`/api/v1/roster/shifts/${shiftTemplateId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function getBranchDefaultShift(
  branchId: UUID,
  init?: RequestInit,
): Promise<BranchDefaultShiftOut> {
  return apiJson<BranchDefaultShiftOut>(
    `/api/v1/roster/branches/${branchId}/default-shift`,
    init,
  );
}

export async function setBranchDefaultShift(
  branchId: UUID,
  payload: BranchDefaultShiftUpsertIn,
  init?: RequestInit,
): Promise<BranchDefaultShiftOut> {
  return apiJson<BranchDefaultShiftOut>(
    `/api/v1/roster/branches/${branchId}/default-shift`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
      ...init,
    },
  );
}

export async function listEmployeeAssignments(
  employeeId: UUID,
  init?: RequestInit,
): Promise<ShiftAssignmentOut[]> {
  return apiJson<ShiftAssignmentOut[]>(
    `/api/v1/roster/employees/${employeeId}/assignments`,
    init,
  );
}

export async function createEmployeeAssignment(
  employeeId: UUID,
  payload: ShiftAssignmentCreateIn,
  init?: RequestInit,
): Promise<ShiftAssignmentOut> {
  return apiJson<ShiftAssignmentOut>(
    `/api/v1/roster/employees/${employeeId}/assignments`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      ...init,
    },
  );
}

export async function listEmployeeOverrides(
  args: { employeeId: UUID; from: string; to: string },
  init?: RequestInit,
): Promise<RosterOverrideOut[]> {
  const qs = new URLSearchParams({ from: args.from, to: args.to });
  return apiJson<RosterOverrideOut[]>(
    `/api/v1/roster/employees/${args.employeeId}/overrides?${qs.toString()}`,
    init,
  );
}

export async function upsertEmployeeOverride(
  args: { employeeId: UUID; day: string; payload: RosterOverrideUpsertIn },
  init?: RequestInit,
): Promise<RosterOverrideOut> {
  return apiJson<RosterOverrideOut>(
    `/api/v1/roster/employees/${args.employeeId}/overrides/${args.day}`,
    {
      method: "PUT",
      body: JSON.stringify(args.payload),
      ...init,
    },
  );
}
