import { describe, expect, it } from "vitest";

import { buildAssignmentPayload, buildOverridePayload } from "@/features/roster/forms";

describe("features/roster/forms", () => {
  it("builds an assignment payload", () => {
    expect(
      buildAssignmentPayload({
        shiftTemplateId: "11111111-1111-4111-8111-111111111111",
        effectiveFrom: "2026-01-01",
        effectiveTo: "2026-01-31",
      }),
    ).toEqual({
      shift_template_id: "11111111-1111-4111-8111-111111111111",
      effective_from: "2026-01-01",
      effective_to: "2026-01-31",
    });
  });

  it("rejects overlapping assignment date order", () => {
    expect(() =>
      buildAssignmentPayload({
        shiftTemplateId: "11111111-1111-4111-8111-111111111111",
        effectiveFrom: "2026-01-31",
        effectiveTo: "2026-01-01",
      }),
    ).toThrow("Effective to must be on or after the start date.");
  });

  it("requires a shift for shift-change overrides", () => {
    expect(() =>
      buildOverridePayload({
        overrideType: "SHIFT_CHANGE",
        shiftTemplateId: null,
        notes: "",
      }),
    ).toThrow("Shift template is required for shift changes.");
  });

  it("rejects a shift on non-shift override types", () => {
    expect(() =>
      buildOverridePayload({
        overrideType: "WEEKOFF",
        shiftTemplateId: "11111111-1111-4111-8111-111111111111",
        notes: "",
      }),
    ).toThrow("Shift template is only allowed for shift changes.");
  });
});
