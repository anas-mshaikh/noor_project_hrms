import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";

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
    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });

    renderWithProviders(<PayrollPayrunsPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Generate payrun" }));
    fireEvent.change(screen.getByLabelText("Calendar"), {
      target: { value: "11111111-1111-4111-8111-111111111111" },
    });
    fireEvent.change(screen.getByLabelText("Period"), {
      target: { value: "2026-03" },
    });
    fireEvent.click(screen.getAllByRole("button", { name: "Generate payrun" })[1]);

    expect(routerPush).toHaveBeenCalledWith(`/payroll/payruns/${PAYRUN_ID}`);
  });
});
