import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";

import type { MeResponse } from "@/lib/types";
import { renderWithProviders } from "@/test/utils/render";
import { routerPush } from "@/test/utils/router";
import { seedSession } from "@/test/utils/selection";

import PayrollStructuresPage from "../page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const STRUCTURE_ID = "f4444444-4444-4444-8444-444444444444";
const SESSION: MeResponse = {
  user: { id: "u-payroll", email: "payroll@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: ["payroll:structure:read", "payroll:structure:write"],
  scope: {
    tenant_id: TENANT_ID,
    company_id: null,
    branch_id: null,
    allowed_tenant_ids: [TENANT_ID],
    allowed_company_ids: [],
    allowed_branch_ids: [],
  },
};

describe("/payroll/structures", () => {
  it("creates a structure and navigates to detail", async () => {
    seedSession(SESSION);
    renderWithProviders(<PayrollStructuresPage />);

    fireEvent.click(screen.getByRole("button", { name: "Create structure" }));
    fireEvent.change(screen.getByLabelText("Code"), { target: { value: "STD" } });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Standard Structure" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Create structure" })[1]);

    expect(routerPush).toHaveBeenCalledWith(`/payroll/structures/${STRUCTURE_ID}`);
  });
});
