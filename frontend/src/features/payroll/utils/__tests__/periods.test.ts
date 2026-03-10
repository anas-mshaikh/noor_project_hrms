import { describe, expect, it } from "vitest";

import { currentPayrollYear, isValidPeriodKey, yearFromPeriodKey } from "@/features/payroll/utils/periods";

describe("features/payroll/utils/periods", () => {
  it("returns the current year from a date", () => {
    expect(currentPayrollYear(new Date("2026-03-11T00:00:00Z"))).toBe(2026);
  });

  it("validates and extracts period keys", () => {
    expect(isValidPeriodKey("2026-03")).toBe(true);
    expect(isValidPeriodKey("2026-3")).toBe(false);
    expect(yearFromPeriodKey("2026-03")).toBe(2026);
    expect(yearFromPeriodKey("bad-key")).toBeNull();
  });
});
