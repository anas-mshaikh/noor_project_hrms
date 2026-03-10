import type { PayableDaySummaryOut, UUID } from "@/lib/types";
import { parseYmdLocal } from "@/lib/dateRange";

export function validatePayablesRange(args: {
  from: string;
  to: string;
  maxDays: number;
}): string | null {
  const from = parseYmdLocal(args.from);
  const to = parseYmdLocal(args.to);
  if (!from || !to) return "Enter a valid date range.";
  if (from > to) return "From date must be on or before the to date.";
  const msPerDay = 24 * 60 * 60 * 1000;
  const diffDays = Math.floor((to.getTime() - from.getTime()) / msPerDay) + 1;
  if (diffDays > args.maxDays) {
    return `Range cannot exceed ${args.maxDays} days.`;
  }
  return null;
}

export type TeamPayablesSummary = {
  employeeId: UUID;
  branchId: UUID;
  totalDays: number;
  payableMinutes: number;
  workedMinutes: number;
  expectedMinutes: number;
  presentDays: number;
  absentDays: number;
  rows: PayableDaySummaryOut[];
  computedAt: string;
};

export function aggregateTeamPayables(
  rows: PayableDaySummaryOut[],
): TeamPayablesSummary[] {
  const map = new Map<UUID, TeamPayablesSummary>();
  for (const row of rows) {
    const current = map.get(row.employee_id) ?? {
      employeeId: row.employee_id,
      branchId: row.branch_id,
      totalDays: 0,
      payableMinutes: 0,
      workedMinutes: 0,
      expectedMinutes: 0,
      presentDays: 0,
      absentDays: 0,
      rows: [],
      computedAt: row.computed_at,
    };
    current.totalDays += 1;
    current.payableMinutes += row.payable_minutes;
    current.workedMinutes += row.worked_minutes;
    current.expectedMinutes += row.expected_minutes;
    if (row.presence_status === "PRESENT") current.presentDays += 1;
    if (row.presence_status === "ABSENT") current.absentDays += 1;
    current.rows.push(row);
    if (row.computed_at > current.computedAt) current.computedAt = row.computed_at;
    map.set(row.employee_id, current);
  }
  return Array.from(map.values()).sort((a, b) => a.employeeId.localeCompare(b.employeeId));
}
