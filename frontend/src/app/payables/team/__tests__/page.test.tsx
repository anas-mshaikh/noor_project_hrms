import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import type { MeResponse, PayableDaysOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";

import PayablesTeamPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-mgr", email: "manager@example.com", status: "ACTIVE" },
  roles: ["MANAGER"],
  permissions: ["attendance:payable:team:read", "workflow:request:read"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: null,
    branch_id: null,
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: [],
    allowed_branch_ids: [],
  },
};

describe("/payables/team", () => {
  it("re-queries on depth changes and shows aggregated rows", async () => {
    const depths: string[] = [];

    server.use(
      http.get("*/api/v1/attendance/team/payable-days", ({ request }) => {
        const url = new URL(request.url);
        const depth = url.searchParams.get("depth") ?? "1";
        depths.push(depth);
        const out: PayableDaysOut = {
          items:
            depth === "all"
              ? [
                  {
                    day: "2026-01-01",
                    employee_id: "11111111-1111-4111-8111-111111111111",
                    branch_id: "22222222-2222-4222-8222-222222222222",
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
                  {
                    day: "2026-01-01",
                    employee_id: "33333333-3333-4333-8333-333333333333",
                    branch_id: "22222222-2222-4222-8222-222222222222",
                    shift_template_id: null,
                    day_type: "WORKDAY",
                    presence_status: "ABSENT",
                    expected_minutes: 480,
                    worked_minutes: 0,
                    payable_minutes: 0,
                    anomalies_json: null,
                    source_breakdown: null,
                    computed_at: new Date(0).toISOString(),
                  },
                ]
              : [
                  {
                    day: "2026-01-01",
                    employee_id: "11111111-1111-4111-8111-111111111111",
                    branch_id: "22222222-2222-4222-8222-222222222222",
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
        };
        return HttpResponse.json(ok(out));
      }),
    );

    seedSession(SESSION);
    renderWithProviders(<PayablesTeamPage />);

    expect(await screen.findByText("11111111-1111-4111-8111-111111111111")).toBeVisible();
    expect(screen.queryByText("33333333-3333-4333-8333-333333333333")).toBeNull();

    fireEvent.change(screen.getByLabelText("Depth"), { target: { value: "all" } });

    expect(await screen.findByText("33333333-3333-4333-8333-333333333333")).toBeVisible();
    await waitFor(() => {
      expect(depths).toEqual(["1", "all"]);
    });
  });
});
