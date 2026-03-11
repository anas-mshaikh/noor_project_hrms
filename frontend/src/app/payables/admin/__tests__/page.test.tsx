import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import type { EmployeeDirectoryRowOut, MeResponse, PayableDaySummaryListOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope, seedSession } from "@/test/utils/selection";

import PayablesAdminPage from "../page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const COMPANY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const BRANCH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const EMPLOYEE_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

const SESSION: MeResponse = {
  user: { id: "u-hr", email: "hr@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: ["attendance:payable:admin:read", "attendance:payable:recompute", "hr:employee:read"],
  scope: {
    tenant_id: TENANT_ID,
    company_id: COMPANY_ID,
    branch_id: BRANCH_ID,
    allowed_tenant_ids: [TENANT_ID],
    allowed_company_ids: [COMPANY_ID],
    allowed_branch_ids: [BRANCH_ID],
  },
};

function employeeRow(): EmployeeDirectoryRowOut {
  return {
    employee_id: EMPLOYEE_ID,
    employee_code: "E0001",
    status: "ACTIVE",
    full_name: "Alice One",
    email: "alice@example.com",
    phone: null,
    branch_id: BRANCH_ID,
    org_unit_id: null,
    manager_employee_id: null,
    manager_name: null,
  };
}

describe("/payables/admin", () => {
  it("fails closed without branch scope", async () => {
    seedSession({
      ...SESSION,
      scope: {
        ...SESSION.scope,
        company_id: null,
        branch_id: null,
        allowed_company_ids: [],
        allowed_branch_ids: [],
      },
    });
    seedScope({ tenantId: TENANT_ID });

    renderWithProviders(<PayablesAdminPage />);

    expect(await screen.findByText("Admin payable summaries are limited to the active branch scope.")).toBeVisible();
  });

  it("supports load more and recompute", async () => {
    const recomputes: Array<Record<string, unknown>> = [];

    server.use(
      http.get("*/api/v1/hr/employees", () =>
        HttpResponse.json(ok({ items: [employeeRow()], paging: { limit: 8, offset: 0, total: 1 } })),
      ),
      http.get("*/api/v1/attendance/admin/payable-days", ({ request }) => {
        const url = new URL(request.url);
        const cursor = url.searchParams.get("cursor");
        const out: PayableDaySummaryListOut = cursor
          ? {
              items: [
                {
                  day: "2026-01-02",
                  employee_id: EMPLOYEE_ID,
                  branch_id: BRANCH_ID,
                  shift_template_id: null,
                  day_type: "WORKDAY",
                  presence_status: "PRESENT",
                  expected_minutes: 480,
                  worked_minutes: 470,
                  payable_minutes: 470,
                  anomalies_json: null,
                  source_breakdown: null,
                  computed_at: new Date(0).toISOString(),
                },
              ],
              next_cursor: null,
            }
          : {
              items: [
                {
                  day: "2026-01-03",
                  employee_id: EMPLOYEE_ID,
                  branch_id: BRANCH_ID,
                  shift_template_id: null,
                  day_type: "WORKDAY",
                  presence_status: "PRESENT",
                  expected_minutes: 480,
                  worked_minutes: 480,
                  payable_minutes: 480,
                  anomalies_json: null,
                  source_breakdown: null,
                  computed_at: new Date(0).toISOString(),
                },
              ],
              next_cursor: "2026-01-03|dddddddd-dddd-4ddd-8ddd-dddddddddddd",
            };
        return HttpResponse.json(ok(out));
      }),
      http.post("*/api/v1/attendance/payable/recompute", async ({ request }) => {
        recomputes.push((await request.json()) as Record<string, unknown>);
        return HttpResponse.json(ok({ computed_rows: 2 }));
      }),
    );

    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });

    renderWithProviders(<PayablesAdminPage />);

    expect((await screen.findAllByText("2026-01-03")).length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "Load more" }));
    expect((await screen.findAllByText("2026-01-02")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "Recompute" }));
    await waitFor(() => {
      expect(recomputes).toEqual([
        expect.objectContaining({ from: expect.any(String), to: expect.any(String), branch_id: BRANCH_ID }),
      ]);
    });
  });
});
