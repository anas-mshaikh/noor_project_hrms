import { describe, expect, it } from "vitest";

import { workflowRequestTypeLabel } from "@/features/workflow/requestTypes";

describe("features/workflow/requestTypes", () => {
  it("maps DOCUMENT_VERIFICATION to a friendly label", () => {
    expect(workflowRequestTypeLabel("DOCUMENT_VERIFICATION")).toBe("Document verification");
  });

  it("maps PAYRUN_APPROVAL to a friendly label", () => {
    expect(workflowRequestTypeLabel("PAYRUN_APPROVAL")).toBe("Payrun approval");
  });
});
