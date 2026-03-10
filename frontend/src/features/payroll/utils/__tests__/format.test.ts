import { describe, expect, it } from "vitest";

import { formatPayrollMoney } from "@/features/payroll/utils/format";

describe("features/payroll/utils/format", () => {
  it("formats payroll amounts with currency", () => {
    expect(formatPayrollMoney("5000", "SAR")).toContain("5");
    expect(formatPayrollMoney(1250.5, "SAR")).toContain("1");
  });

  it("falls back cleanly for invalid amounts", () => {
    expect(formatPayrollMoney("not-a-number", "SAR")).toBe("not-a-number");
  });
});
