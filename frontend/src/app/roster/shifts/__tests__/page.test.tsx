import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { MeResponse, ShiftTemplateOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope, seedSession } from "@/test/utils/selection";

import RosterShiftsPage from "../page";

const BRANCH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const COMPANY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";

const SESSION: MeResponse = {
  user: { id: "u-hr", email: "hr@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: ["roster:shift:read", "roster:shift:write"],
  scope: {
    tenant_id: TENANT_ID,
    company_id: COMPANY_ID,
    branch_id: BRANCH_ID,
    allowed_tenant_ids: [TENANT_ID],
    allowed_company_ids: [COMPANY_ID],
    allowed_branch_ids: [BRANCH_ID],
  },
};

function shift(name = "Day Shift", code = "DAY"): ShiftTemplateOut {
  const now = new Date(0).toISOString();
  return {
    id:
      code === "DAY"
        ? "11111111-1111-4111-8111-111111111111"
        : "22222222-2222-4222-8222-222222222222",
    tenant_id: TENANT_ID,
    branch_id: BRANCH_ID,
    code,
    name,
    start_time: "09:00:00",
    end_time: "18:00:00",
    break_minutes: 60,
    grace_minutes: 10,
    min_full_day_minutes: 480,
    is_active: true,
    expected_minutes: 480,
    created_by_user_id: null,
    created_at: now,
    updated_at: now,
  };
}

describe("/roster/shifts", () => {
  it("renders empty state when no shifts exist", async () => {
    server.use(
      http.get(`*/api/v1/roster/branches/${BRANCH_ID}/shifts`, () => HttpResponse.json(ok([]))),
    );

    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });

    renderWithProviders(<RosterShiftsPage />);

    expect(await screen.findByText("No shift templates")).toBeVisible();
  });

  it("creates and edits a shift template", async () => {
    const user = userEvent.setup();
    const shifts: ShiftTemplateOut[] = [];

    server.use(
      http.get(`*/api/v1/roster/branches/${BRANCH_ID}/shifts`, () => HttpResponse.json(ok(shifts))),
      http.post(`*/api/v1/roster/branches/${BRANCH_ID}/shifts`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created = shift(String(body.name ?? "Day Shift"), String(body.code ?? "DAY"));
        shifts.push(created);
        return HttpResponse.json(ok(created));
      }),
      http.patch("*/api/v1/roster/shifts/:shiftTemplateId", async ({ request, params }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const idx = shifts.findIndex((item) => item.id === String(params.shiftTemplateId));
        shifts[idx] = {
          ...shifts[idx],
          name: String(body.name ?? shifts[idx].name),
          code: String(body.code ?? shifts[idx].code),
        };
        return HttpResponse.json(ok(shifts[idx]));
      }),
    );

    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });

    renderWithProviders(<RosterShiftsPage />);

    await user.click(await screen.findByRole("button", { name: "Create shift" }));
    const createDialog = await screen.findByRole("dialog");
    await user.type(within(createDialog).getByLabelText("Code"), "DAY");
    await user.type(within(createDialog).getByLabelText("Name"), "Day Shift");
    await user.click(within(createDialog).getByRole("button", { name: "Create shift" }));

    const table = await screen.findByRole("table");
    expect(await within(table).findByText("Day Shift")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Edit shift" }));
    const editDialog = await screen.findByRole("dialog");
    await user.clear(within(editDialog).getByLabelText("Name"));
    await user.type(within(editDialog).getByLabelText("Name"), "Updated Day Shift");
    await user.click(within(editDialog).getByRole("button", { name: "Save changes" }));

    expect(await within(table).findByText("Updated Day Shift")).toBeVisible();
  }, 30_000);
});
