import { apiJson } from "@/lib/api";
import type { MssEmployeeProfileOut, MssTeamListOut, UUID } from "@/lib/types";

/**
 * MSS API wrapper (manager self service).
 */

export async function listTeam(
  args: {
    depth: "1" | "all" | string;
    q?: string | null;
    status?: string | null;
    branchId?: UUID | null;
    orgUnitId?: UUID | null;
    limit: number;
    offset: number;
  },
  init?: RequestInit
): Promise<MssTeamListOut> {
  const qs = new URLSearchParams({
    depth: args.depth,
    limit: String(args.limit),
    offset: String(args.offset),
  });
  if (args.q) qs.set("q", args.q);
  if (args.status) qs.set("status", args.status);
  if (args.branchId) qs.set("branch_id", args.branchId);
  if (args.orgUnitId) qs.set("org_unit_id", args.orgUnitId);

  return apiJson<MssTeamListOut>(`/api/v1/mss/team?${qs.toString()}`, init);
}

export async function getTeamMember(
  employeeId: UUID,
  init?: RequestInit
): Promise<MssEmployeeProfileOut> {
  return apiJson<MssEmployeeProfileOut>(`/api/v1/mss/team/${employeeId}`, init);
}

