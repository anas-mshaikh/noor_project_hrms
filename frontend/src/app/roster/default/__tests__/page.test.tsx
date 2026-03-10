import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { MeResponse } from "@/lib/types";
import { fail, ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope, seedSession } from "@/test/utils/selection";

import RosterDefaultPage from "../page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const COMPANY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const BRANCH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const SHIFT_ID = "11111111-1111-4111-8111-111111111111";

const SESSION: MeResponse = {
  user: { id: "u-hr", email: "hr@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: ["roster:shift:read", "roster:defaults:write"],
  scope: {
    tenant_id: TENANT_ID,
    company_id: COMPANY_ID,
    branch_id: BRANCH_ID,
    allowed_tenant_ids: [TENANT_ID],
    allowed_company_ids: [COMPANY_ID],
    allowed_branch_ids: [BRANCH_ID],
  },
};

const SHIFT = {
  id: SHIFT_ID,
  tenant_id: TENANT_ID,
  branch_id: BRANCH_ID,
  code: "DAY",
  name: "Day Shift",
  start_time: "09:00:00",
  end_time: "18:00:00",
  break_minutes: 60,
  grace_minutes: 10,
  min_full_day_minutes: 480,
  is_active: true,
  expected_minutes: 480,
  created_by_user_id: null,
  created_at: new Date(0).toISOString(),
  updated_at: new Date(0).toISOString(),
};

describe("/roster/default", () => {
  it("shows an empty state when no shift templates exist", async () => {
    server.use(
      http.get(`*/api/v1/roster/branches/${BRANCH_ID}/shifts`, () => HttpResponse.json(ok([]))),
    );

    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });

    renderWithProviders(<RosterDefaultPage />);

    expect(await screen.findByText("No shift templates")).toBeVisible();
  });

  it("sets the branch default shift", async () => {
    let currentDefaultId: string | null = null;

    server.use(
      http.get(`*/api/v1/roster/branches/${BRANCH_ID}/shifts`, () => HttpResponse.json(ok([SHIFT]))),
      http.get(`*/api/v1/roster/branches/${BRANCH_ID}/default-shift`, () => {
        if (!currentDefaultId) {
          return HttpResponse.json(
            fail("roster.default.not_found", "Not found", { correlation_id: "cid-roster-default" }),
            { status: 404 },
          );
        }
        return HttpResponse.json(
          ok({
            tenant_id: TENANT_ID,
            branch_id: BRANCH_ID,
            default_shift_template_id: currentDefaultId,
            created_at: new Date(0).toISOString(),
            updated_at: new Date(0).toISOString(),
          }),
        );
      }),
      http.put(`*/api/v1/roster/branches/${BRANCH_ID}/default-shift`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        currentDefaultId = String(body.shift_template_id);
        return HttpResponse.json(
          ok({
            tenant_id: TENANT_ID,
            branch_id: BRANCH_ID,
            default_shift_template_id: currentDefaultId,
            created_at: new Date(0).toISOString(),
            updated_at: new Date(0).toISOString(),
          }),
        );
      }),
    );

    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });

    renderWithProviders(<RosterDefaultPage />);

    fireEvent.click(await screen.findByRole("button", { name: "Set default shift" }));
    fireEvent.click(screen.getByRole("button", { name: "Save default" }));

    expect(await screen.findByText("Day Shift")).toBeVisible();
  });

  it("shows access denied without read permission", async () => {
    seedSession({ ...SESSION, permissions: [] });
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });

    renderWithProviders(<RosterDefaultPage />);

    expect(await screen.findByText("Access denied")).toBeVisible();
  });
});
