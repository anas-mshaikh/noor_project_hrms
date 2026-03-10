import { describe, expect, it } from "vitest";

import { canPublishPayrun, canSubmitPayrun } from "@/features/payroll/utils/gates";
import type { PayrunOut } from "@/lib/types";

const basePayrun: PayrunOut = {
  id: "11111111-1111-4111-8111-111111111111",
  tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  calendar_id: "22222222-2222-4222-8222-222222222222",
  period_id: "33333333-3333-4333-8333-333333333333",
  branch_id: "44444444-4444-4444-8444-444444444444",
  version: 1,
  status: "DRAFT",
  generated_at: new Date(0).toISOString(),
  generated_by_user_id: null,
  workflow_request_id: null,
  idempotency_key: null,
  totals_json: { included_count: 1 },
  created_at: new Date(0).toISOString(),
  updated_at: new Date(0).toISOString(),
};

describe("features/payroll/utils/gates", () => {
  it("allows submit only for draft payruns with included employees", () => {
    expect(canSubmitPayrun(basePayrun)).toBe(true);
    expect(canSubmitPayrun({ ...basePayrun, totals_json: { included_count: 0 } })).toBe(false);
    expect(canSubmitPayrun({ ...basePayrun, status: "PENDING_APPROVAL" })).toBe(false);
  });

  it("allows publish only for approved payruns", () => {
    expect(canPublishPayrun({ ...basePayrun, status: "APPROVED" })).toBe(true);
    expect(canPublishPayrun(basePayrun)).toBe(false);
  });
});
