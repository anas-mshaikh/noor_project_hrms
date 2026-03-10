import { describe, expect, it } from "vitest";
import { screen } from "@testing-library/react";

import type { MeResponse } from "@/lib/types";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope, seedSession } from "@/test/utils/selection";

import PayrollHomePage from "../page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const COMPANY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const BRANCH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";

const SESSION: MeResponse = {
  user: { id: "u-payroll", email: "payroll@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: [
    "payroll:calendar:read",
    "payroll:component:read",
    "payroll:structure:read",
    "payroll:compensation:read",
    "payroll:payrun:read",
  ],
  scope: {
    tenant_id: TENANT_ID,
    company_id: COMPANY_ID,
    branch_id: BRANCH_ID,
    allowed_tenant_ids: [TENANT_ID],
    allowed_company_ids: [COMPANY_ID],
    allowed_branch_ids: [BRANCH_ID],
  },
};

describe("/payroll", () => {
  it("renders the payroll checklist and setup links", async () => {
    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });

    renderWithProviders(<PayrollHomePage />);

    expect(await screen.findByRole("heading", { name: "Payroll" })).toBeVisible();
    expect(screen.getByText("Setup checklist")).toBeVisible();
    expect(screen.getByRole("link", { name: /Calendars and periods/i })).toHaveAttribute(
      "href",
      "/payroll/calendars",
    );
    expect(screen.getByRole("link", { name: /Components/i })).toHaveAttribute(
      "href",
      "/payroll/components",
    );
    expect(screen.getByRole("link", { name: /Payruns/i })).toHaveAttribute(
      "href",
      "/payroll/payruns",
    );
  });
});
