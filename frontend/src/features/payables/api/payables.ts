import { apiJson } from "@/lib/api";
import type {
  PayableDaySummaryListOut,
  PayableDaysOut,
  PayableRecomputeIn,
  PayableRecomputeOut,
  UUID,
} from "@/lib/types";

export async function getMyPayableDays(
  args: { from: string; to: string },
  init?: RequestInit,
): Promise<PayableDaysOut> {
  const qs = new URLSearchParams({ from: args.from, to: args.to });
  return apiJson<PayableDaysOut>(`/api/v1/attendance/me/payable-days?${qs.toString()}`, init);
}

export async function getTeamPayableDays(
  args: { from: string; to: string; depth: "1" | "all" },
  init?: RequestInit,
): Promise<PayableDaysOut> {
  const qs = new URLSearchParams({ from: args.from, to: args.to, depth: args.depth });
  return apiJson<PayableDaysOut>(`/api/v1/attendance/team/payable-days?${qs.toString()}`, init);
}

export async function getAdminPayableDays(
  args: {
    from: string;
    to: string;
    branchId: UUID;
    employeeId?: UUID | null;
    limit: number;
    cursor?: string | null;
  },
  init?: RequestInit,
): Promise<PayableDaySummaryListOut> {
  const qs = new URLSearchParams({
    from: args.from,
    to: args.to,
    branch_id: args.branchId,
    limit: String(args.limit),
  });
  if (args.employeeId) qs.set("employee_id", args.employeeId);
  if (args.cursor) qs.set("cursor", args.cursor);
  return apiJson<PayableDaySummaryListOut>(
    `/api/v1/attendance/admin/payable-days?${qs.toString()}`,
    init,
  );
}

export async function recomputePayableDays(
  payload: PayableRecomputeIn,
  init?: RequestInit,
): Promise<PayableRecomputeOut> {
  return apiJson<PayableRecomputeOut>("/api/v1/attendance/payable/recompute", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}
