import { describe, expect, it } from "vitest";

import { dmsStatusLabel } from "@/features/dms/status";

describe("features/dms/status", () => {
  it("maps known DMS statuses to readable labels", () => {
    expect(dmsStatusLabel("DRAFT")).toBe("Draft");
    expect(dmsStatusLabel("SUBMITTED")).toBe("Submitted");
    expect(dmsStatusLabel("VERIFIED")).toBe("Verified");
    expect(dmsStatusLabel("REJECTED")).toBe("Rejected");
    expect(dmsStatusLabel("EXPIRED")).toBe("Expired");
  });
});
