import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import userEvent from "@testing-library/user-event";

import type { MeResponse, PayrollComponentOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";

import PayrollComponentsPage from "../page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const SESSION: MeResponse = {
  user: { id: "u-payroll", email: "payroll@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: ["payroll:component:read", "payroll:component:write"],
  scope: {
    tenant_id: TENANT_ID,
    company_id: null,
    branch_id: null,
    allowed_tenant_ids: [TENANT_ID],
    allowed_company_ids: [],
    allowed_branch_ids: [],
  },
};

function component(code = "BASIC", name = "Basic Salary"): PayrollComponentOut {
  const now = new Date(0).toISOString();
  return {
    id: "33333333-3333-4333-8333-333333333333",
    tenant_id: TENANT_ID,
    code,
    name,
    component_type: "EARNING",
    calc_mode: "FIXED",
    default_amount: "5000.00",
    default_percent: null,
    is_taxable: false,
    is_active: true,
    created_at: now,
    updated_at: now,
  };
}

describe("/payroll/components", () => {
  it("creates a payroll component", async () => {
    const user = userEvent.setup();
    const items: PayrollComponentOut[] = [];

    server.use(
      http.get("*/api/v1/payroll/components", ({ request }) => {
        const type = new URL(request.url).searchParams.get("type");
        const filtered = type ? items.filter((item) => item.component_type === type) : items;
        return HttpResponse.json(ok(filtered));
      }),
      http.post("*/api/v1/payroll/components", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created = component(String(body.code ?? "BASIC"), String(body.name ?? "Basic Salary"));
        items.push(created);
        return HttpResponse.json(ok(created));
      }),
    );

    seedSession(SESSION);
    renderWithProviders(<PayrollComponentsPage />);

    expect(await screen.findByText("No payroll components")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Create component" }));
    const dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Code"), "BASIC");
    await user.type(within(dialog).getByLabelText("Name"), "Basic Salary");
    await user.click(within(dialog).getByRole("button", { name: "Create component" }));

    expect(await screen.findByRole("cell", { name: "Basic Salary" })).toBeVisible();
    expect(await screen.findByText("Calc mode: FIXED")).toBeVisible();
  }, 30_000);
});
