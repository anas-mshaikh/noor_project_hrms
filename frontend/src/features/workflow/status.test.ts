import { describe, expect, it } from "vitest";

import { workflowStatusLabel, workflowStatusParam } from "./status";

describe("features/workflow/status", () => {
  it("maps workflow statuses to human labels", () => {
    expect(workflowStatusLabel("PENDING")).toBe("Pending");
    expect(workflowStatusLabel("approved")).toBe("Approved");
    expect(workflowStatusLabel("REJECTED")).toBe("Rejected");
    expect(workflowStatusLabel("CANCELED")).toBe("Canceled");
  });

  it("maps workflow statuses to backend query param values", () => {
    expect(workflowStatusParam("PENDING")).toBe("pending");
    expect(workflowStatusParam("APPROVED")).toBe("approved");
    expect(workflowStatusParam("REJECTED")).toBe("rejected");
    expect(workflowStatusParam("CANCELED")).toBe("canceled");
    expect(workflowStatusParam("DRAFT")).toBe("draft");
  });
});
