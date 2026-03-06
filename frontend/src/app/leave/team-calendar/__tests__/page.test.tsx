import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import type { MeResponse, TeamCalendarOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope, seedSession } from "@/test/utils/selection";

import LeaveTeamCalendarPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-mgr", email: "manager@example.com", status: "ACTIVE" },
  roles: ["MANAGER"],
  permissions: ["leave:team:read"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

describe("/leave/team-calendar", () => {
  it("renders the calendar and supports depth switching", async () => {
    const depths: string[] = [];

    server.use(
      http.get("*/api/v1/leave/team/calendar", ({ request }) => {
        const url = new URL(request.url);
        const depth = url.searchParams.get("depth") ?? "";
        depths.push(depth);

        const from = url.searchParams.get("from") ?? "2026-01-01";

        const out: TeamCalendarOut = {
          items:
            depth === "all"
              ? [
                  {
                    leave_request_id: "11111111-1111-4111-8111-111111111111",
                    employee_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    start_date: from,
                    end_date: from,
                    leave_type_code: "AL",
                    requested_days: 1,
                  },
                  {
                    leave_request_id: "22222222-2222-4222-8222-222222222222",
                    employee_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                    start_date: from,
                    end_date: from,
                    leave_type_code: "SL",
                    requested_days: 1,
                  },
                ]
              : [
                  {
                    leave_request_id: "11111111-1111-4111-8111-111111111111",
                    employee_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                    start_date: from,
                    end_date: from,
                    leave_type_code: "AL",
                    requested_days: 1,
                  },
                ],
        };

        return HttpResponse.json(ok(out));
      })
    );

    seedSession(SESSION);
    seedScope({
      tenantId: SESSION.scope.tenant_id,
      companyId: SESSION.scope.company_id,
      branchId: SESSION.scope.branch_id,
    });

    renderWithProviders(<LeaveTeamCalendarPage />);

    expect(await screen.findByRole("heading", { name: "Team Calendar" })).toBeVisible();
    expect(await screen.findByText("AL (1)")).toBeVisible();
    expect(screen.queryByText("SL (1)")).toBeNull();

    fireEvent.change(screen.getByLabelText("Depth"), { target: { value: "all" } });

    expect(await screen.findByText("SL (1)")).toBeVisible();

    await waitFor(() => {
      expect(depths).toEqual(["1", "all"]);
    });
  });
});
