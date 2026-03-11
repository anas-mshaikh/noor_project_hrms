import { describe, expect, it } from "vitest";
import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import userEvent from "@testing-library/user-event";

import type {
  MeResponse,
  PayrollComponentOut,
  SalaryStructureDetailOut,
  SalaryStructureLineOut,
} from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { setParams, setPathname } from "@/test/utils/router";
import { seedSession } from "@/test/utils/selection";

import PayrollStructureDetailPage from "../page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const STRUCTURE_ID = "44444444-4444-4444-8444-444444444444";
const COMPONENT_ID = "33333333-3333-4333-8333-333333333333";
const SESSION: MeResponse = {
  user: { id: "u-payroll", email: "payroll@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: ["payroll:structure:read", "payroll:structure:write", "payroll:component:read"],
  scope: {
    tenant_id: TENANT_ID,
    company_id: null,
    branch_id: null,
    allowed_tenant_ids: [TENANT_ID],
    allowed_company_ids: [],
    allowed_branch_ids: [],
  },
};

function component(): PayrollComponentOut {
  const now = new Date(0).toISOString();
  return {
    id: COMPONENT_ID,
    tenant_id: TENANT_ID,
    code: "BASIC",
    name: "Basic Salary",
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

function line(sortOrder = 10): SalaryStructureLineOut {
  return {
    id: "55555555-5555-4555-8555-555555555555",
    tenant_id: TENANT_ID,
    salary_structure_id: STRUCTURE_ID,
    component_id: COMPONENT_ID,
    sort_order: sortOrder,
    calc_mode_override: null,
    amount_override: null,
    percent_override: null,
    created_at: new Date(0).toISOString(),
  };
}

function detail(lines: SalaryStructureLineOut[]): SalaryStructureDetailOut {
  const now = new Date(0).toISOString();
  return {
    structure: {
      id: STRUCTURE_ID,
      tenant_id: TENANT_ID,
      code: "STD",
      name: "Standard Structure",
      is_active: true,
      created_at: now,
      updated_at: now,
    },
    lines,
  };
}

describe("/payroll/structures/[structureId]", () => {
  it("fails closed for invalid structure ids", async () => {
    seedSession(SESSION);
    setPathname("/payroll/structures/not-a-uuid");
    setParams({ structureId: "not-a-uuid" });

    renderWithProviders(<PayrollStructureDetailPage params={{ structureId: "not-a-uuid" }} />);

    expect(await screen.findByText("Invalid structure id")).toBeVisible();
  });

  it("loads structure detail and adds a line", async () => {
    const user = userEvent.setup();
    const lines: SalaryStructureLineOut[] = [];

    server.use(
      http.get(`*/api/v1/payroll/salary-structures/${STRUCTURE_ID}`, () =>
        HttpResponse.json(ok(detail(lines))),
      ),
      http.get("*/api/v1/payroll/components", () => HttpResponse.json(ok([component()]))),
      http.post(`*/api/v1/payroll/salary-structures/${STRUCTURE_ID}/lines`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created = line(Number(body.sort_order ?? 10));
        lines.push(created);
        return HttpResponse.json(ok(created));
      }),
    );

    seedSession(SESSION);
    setPathname(`/payroll/structures/${STRUCTURE_ID}`);
    setParams({ structureId: STRUCTURE_ID });

    renderWithProviders(<PayrollStructureDetailPage params={{ structureId: STRUCTURE_ID }} />);

    expect(await screen.findByText("No structure lines")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Add line" }));
    const dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Component"), COMPONENT_ID);
    await user.clear(within(dialog).getByLabelText("Sort order"));
    await user.type(within(dialog).getByLabelText("Sort order"), "10");
    await user.click(within(dialog).getByRole("button", { name: "Add line" }));

    const table = await screen.findByRole("table");
    expect(await within(table).findByText("Basic Salary")).toBeVisible();
    expect(await within(table).findByText("BASIC")).toBeVisible();
  }, 30_000);
});
