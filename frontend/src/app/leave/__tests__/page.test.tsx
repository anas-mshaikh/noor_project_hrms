import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { LeaveBalancesOut, LeaveRequestListOut, LeaveRequestOut, MeResponse } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope, seedSession } from "@/test/utils/selection";

import LeavePage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-emp", email: "employee@example.com", status: "ACTIVE" },
  roles: ["EMPLOYEE"],
  permissions: ["leave:balance:read", "leave:request:read", "leave:request:submit"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

describe("/leave", () => {
  it("loads balances and submits a leave request", async () => {
    const WORKFLOW_ID = "22222222-2222-4222-8222-222222222222";
    const items: LeaveRequestOut[] = [];

    server.use(
      http.get("*/api/v1/leave/me/balances", () => {
        const out: LeaveBalancesOut = {
          items: [
            {
              leave_type_code: "AL",
              leave_type_name: "Annual Leave",
              period_year: 2026,
              balance_days: 10,
              used_days: 0,
              pending_days: 0,
            },
          ],
        };
        return HttpResponse.json(ok(out));
      }),
      http.get("*/api/v1/leave/me/requests", () => {
        const out: LeaveRequestListOut = { items, next_cursor: null };
        return HttpResponse.json(ok(out));
      }),
      http.post("*/api/v1/leave/me/requests", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        expect(body.leave_type_code).toBe("AL");
        expect(body.start_date).toBe("2026-03-10");
        expect(body.end_date).toBe("2026-03-12");
        expect(body.unit).toBe("DAY");

        const created: LeaveRequestOut = {
          id: "11111111-1111-4111-8111-111111111111",
          tenant_id: "t-1",
          employee_id: "e-1",
          company_id: SESSION.scope.company_id,
          branch_id: SESSION.scope.branch_id,
          leave_type_code: "AL",
          leave_type_name: "Annual Leave",
          policy_id: "33333333-3333-4333-8333-333333333333",
          start_date: "2026-03-10",
          end_date: "2026-03-12",
          unit: "DAY",
          half_day_part: null,
          requested_days: 3,
          reason: null,
          status: "PENDING",
          workflow_request_id: WORKFLOW_ID,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        };
        items.unshift(created);
        return HttpResponse.json(ok(created));
      })
    );

    seedSession(SESSION);
    seedScope({
      tenantId: SESSION.scope.tenant_id,
      companyId: SESSION.scope.company_id,
      branchId: SESSION.scope.branch_id,
    });

    renderWithProviders(<LeavePage />);

    // Balances card
    const year = new Date().getFullYear();
    expect(await screen.findByText(`Balances (${year})`)).toBeVisible();
    expect(await screen.findByText("Annual Leave")).toBeVisible();

    // Open apply sheet
    fireEvent.click(screen.getByRole("button", { name: "Apply leave" }));
    expect(await screen.findByText("Submit a leave request for approval.")).toBeVisible();

    // Fill fields
    fireEvent.change(screen.getByLabelText("Leave type"), { target: { value: "AL" } });
    fireEvent.change(screen.getByLabelText("Start"), { target: { value: "2026-03-10" } });
    fireEvent.change(screen.getByLabelText("End"), { target: { value: "2026-03-12" } });

    fireEvent.click(screen.getByRole("button", { name: "Submit request" }));

    // Request should appear in the table after invalidation/refetch.
    expect(await screen.findByRole("button", { name: "AL" })).toBeVisible();
  });
});
