import { describe, expect, it } from "vitest";

import { requestedOverrideForCorrectionType } from "./correctionMapping";

describe("features/attendance/correctionMapping", () => {
  it("maps correction types to requested override statuses", () => {
    expect(requestedOverrideForCorrectionType("MARK_PRESENT")).toBe("PRESENT_OVERRIDE");
    expect(requestedOverrideForCorrectionType("MARK_ABSENT")).toBe("ABSENT_OVERRIDE");
    expect(requestedOverrideForCorrectionType("WFH")).toBe("WFH");
    expect(requestedOverrideForCorrectionType("ON_DUTY")).toBe("ON_DUTY");
  });

  it("defaults MISSED_PUNCH to PRESENT_OVERRIDE", () => {
    expect(requestedOverrideForCorrectionType("MISSED_PUNCH")).toBe("PRESENT_OVERRIDE");
  });
});

