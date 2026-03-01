import { describe, expect, it } from "vitest";

import { clearScope, seedScope } from "@/test/utils/selection";

describe("test/utils/selection", () => {
  it("seedScope writes localStorage + cookie mirror keys", () => {
    seedScope({ tenantId: "t-1", companyId: "c-1", branchId: "b-1" });

    const raw = window.localStorage.getItem("attendance-admin-selection");
    expect(raw).toBeTruthy();
    const parsed = JSON.parse(String(raw)) as { state?: Record<string, unknown> };
    expect(parsed.state?.tenantId).toBe("t-1");
    expect(parsed.state?.companyId).toBe("c-1");
    expect(parsed.state?.branchId).toBe("b-1");

    expect(document.cookie).toContain("noor_scope_tenant_id=t-1");
    expect(document.cookie).toContain("noor_scope_company_id=c-1");
    expect(document.cookie).toContain("noor_scope_branch_id=b-1");
  });

  it("clearScope removes cookie mirror keys", () => {
    seedScope({ tenantId: "t-1", companyId: "c-1", branchId: "b-1" });
    clearScope();

    expect(document.cookie).not.toContain("noor_scope_tenant_id=");
    expect(document.cookie).not.toContain("noor_scope_company_id=");
    expect(document.cookie).not.toContain("noor_scope_branch_id=");
  });
});

