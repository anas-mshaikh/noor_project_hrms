import { apiJson } from "@/lib/api";
import type {
  LeaveBalancesOut,
  LeaveRequestCreateIn,
  LeaveRequestListOut,
  LeaveRequestOut,
  TeamCalendarOut,
  UUID,
} from "@/lib/types";

/**
 * Leave API wrapper (ESS + MSS).
 */

export async function getMyBalances(
  args: { year?: number | null } = {},
  init?: RequestInit,
): Promise<LeaveBalancesOut> {
  const qs = new URLSearchParams();
  if (args.year != null) qs.set("year", String(args.year));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiJson<LeaveBalancesOut>(`/api/v1/leave/me/balances${suffix}`, init);
}

export async function listMyLeaveRequests(
  args: { status?: string | null; limit: number; cursor?: string | null },
  init?: RequestInit,
): Promise<LeaveRequestListOut> {
  const qs = new URLSearchParams({ limit: String(args.limit) });
  if (args.status) qs.set("status", args.status);
  if (args.cursor) qs.set("cursor", args.cursor);
  return apiJson<LeaveRequestListOut>(
    `/api/v1/leave/me/requests?${qs.toString()}`,
    init,
  );
}

export async function submitMyLeaveRequest(
  payload: LeaveRequestCreateIn,
  init?: RequestInit,
): Promise<LeaveRequestOut> {
  return apiJson<LeaveRequestOut>("/api/v1/leave/me/requests", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function cancelMyLeaveRequest(
  leaveRequestId: UUID,
  init?: RequestInit,
): Promise<LeaveRequestOut> {
  return apiJson<LeaveRequestOut>(
    `/api/v1/leave/me/requests/${leaveRequestId}/cancel`,
    {
      method: "POST",
      ...init,
    },
  );
}

export async function getTeamCalendar(
  args: {
    from: string;
    to: string;
    depth: "1" | "all" | string;
    branchId?: UUID | null;
  },
  init?: RequestInit,
): Promise<TeamCalendarOut> {
  const qs = new URLSearchParams({
    from: args.from,
    to: args.to,
    depth: args.depth,
  });
  if (args.branchId) qs.set("branch_id", args.branchId);
  return apiJson<TeamCalendarOut>(
    `/api/v1/leave/team/calendar?${qs.toString()}`,
    init,
  );
}
