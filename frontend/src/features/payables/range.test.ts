import { describe, expect, it } from "vitest";

import type { PayableDaySummaryOut } from "@/lib/types";
import { aggregateTeamPayables, validatePayablesRange } from "@/features/payables/range";

describe("features/payables/range", () => {
  it("validates inclusive bounds", () => {
    expect(validatePayablesRange({ from: "2026-01-01", to: "2026-02-28", maxDays: 62 })).toBeNull();
    expect(validatePayablesRange({ from: "2026-01-01", to: "2026-03-05", maxDays: 62 })).toBe(
      "Range cannot exceed 62 days.",
    );
  });

  it("rejects inverted ranges", () => {
    expect(validatePayablesRange({ from: "2026-01-10", to: "2026-01-01", maxDays: 62 })).toBe(
      "From date must be on or before the to date.",
    );
  });

  it("aggregates team rows by employee", () => {
    const rows: PayableDaySummaryOut[] = [
      {
        day: "2026-01-01",
        employee_id: "11111111-1111-4111-8111-111111111111",
        branch_id: "33333333-3333-4333-8333-333333333333",
        shift_template_id: null,
        day_type: "WORKDAY",
        presence_status: "PRESENT",
        expected_minutes: 480,
        worked_minutes: 480,
        payable_minutes: 480,
        anomalies_json: null,
        source_breakdown: null,
        computed_at: "2026-01-01T00:00:00Z",
      },
      {
        day: "2026-01-02",
        employee_id: "11111111-1111-4111-8111-111111111111",
        branch_id: "33333333-3333-4333-8333-333333333333",
        shift_template_id: null,
        day_type: "WORKDAY",
        presence_status: "ABSENT",
        expected_minutes: 480,
        worked_minutes: 0,
        payable_minutes: 0,
        anomalies_json: null,
        source_breakdown: null,
        computed_at: "2026-01-02T00:00:00Z",
      },
    ];

    expect(aggregateTeamPayables(rows)).toEqual([
      expect.objectContaining({
        employeeId: "11111111-1111-4111-8111-111111111111",
        totalDays: 2,
        presentDays: 1,
        absentDays: 1,
        payableMinutes: 480,
        computedAt: "2026-01-02T00:00:00Z",
      }),
    ]);
  });
});
