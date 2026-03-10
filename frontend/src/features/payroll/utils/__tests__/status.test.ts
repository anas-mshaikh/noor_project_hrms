import { describe, expect, it } from "vitest";

import { payrunAnomalyLabel, payrollStatusLabel } from "@/features/payroll/utils/status";

describe("features/payroll/utils/status", () => {
  it("maps payroll statuses to friendly labels", () => {
    expect(payrollStatusLabel("DRAFT")).toBe("Draft");
    expect(payrollStatusLabel("PENDING_APPROVAL")).toBe("Pending approval");
    expect(payrollStatusLabel("APPROVED")).toBe("Approved");
    expect(payrollStatusLabel("PUBLISHED")).toBe("Published");
    expect(payrollStatusLabel("CANCELLED")).toBe("Canceled");
  });

  it("maps anomaly codes to readable copy", () => {
    expect(payrunAnomalyLabel("NO_COMPENSATION")).toBe("No compensation record");
    expect(payrunAnomalyLabel("CURRENCY_MISMATCH")).toBe("Currency mismatch");
  });
});
