import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { MeResponse } from "@/lib/types";
import { renderWithProviders } from "@/test/utils/render";
import { routerPush } from "@/test/utils/router";
import { seedScope, seedSession } from "@/test/utils/selection";

import PayrollPayrunsPage from "../page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const COMPANY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const BRANCH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const PAYRUN_ID = "77777777-7777-4777-8777-777777777777";
const SESSION: MeResponse = {
  user: { id: "u-payroll", email: "payroll@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: ["payroll:payrun:read", "payroll:payrun:generate", "payroll:calendar:read"],
  scope: {
    tenant_id: TENANT_ID,
    company_id: COMPANY_ID,
    branch_id: BRANCH_ID,
    allowed_tenant_ids: [TENANT_ID],
    allowed_company_ids: [COMPANY_ID],
    allowed_branch_ids: [BRANCH_ID],
  },
};

describe("/payroll/payruns", () => {
  it("generates a payrun and navigates to detail", async () => {
    const user = userEvent.setup();
    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });

    renderWithProviders(<PayrollPayrunsPage />);

    await user.click(await screen.findByRole("button", { name: "Generate payrun" }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(
      within(dialog).getByLabelText("Calendar"),
      "11111111-1111-4111-8111-111111111111"
    );
    await user.selectOptions(within(dialog).getByLabelText("Period"), "2026-03");
    await user.click(within(dialog).getByRole("button", { name: "Generate payrun" }));

    expect(routerPush).toHaveBeenCalledWith(`/payroll/payruns/${PAYRUN_ID}`);
  });
});
