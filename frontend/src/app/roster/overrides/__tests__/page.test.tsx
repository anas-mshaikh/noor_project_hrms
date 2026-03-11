import { describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

vi.mock("@/lib/toastApiError", () => ({ toastApiError: vi.fn() }));

import type { EmployeeDirectoryRowOut, HrEmployee360Out, MeResponse, RosterOverrideOut } from "@/lib/types";
import { toastApiError } from "@/lib/toastApiError";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope, seedSession } from "@/test/utils/selection";
import { setSearchParams } from "@/test/utils/router";

import RosterOverridesPage from "../page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const COMPANY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const BRANCH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const EMPLOYEE_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const SHIFT_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";

const SESSION: MeResponse = {
  user: { id: "u-hr", email: "hr@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: ["roster:override:read", "roster:override:write", "hr:employee:read", "roster:shift:read"],
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

function employee360(): HrEmployee360Out {
  const now = new Date(0).toISOString();
  return {
    employee: {
      id: EMPLOYEE_ID,
      tenant_id: TENANT_ID,
      company_id: COMPANY_ID,
      person_id: "11111111-1111-4111-8111-111111111111",
      employee_code: "E0001",
      status: "ACTIVE",
      join_date: "2026-01-01",
      termination_date: null,
      created_at: now,
      updated_at: now,
    },
    person: {
      id: "11111111-1111-4111-8111-111111111111",
      tenant_id: TENANT_ID,
      first_name: "Alice",
      last_name: "One",
      dob: null,
      nationality: null,
      email: "alice@example.com",
      phone: null,
      address: {},
      created_at: now,
      updated_at: now,
    },
    current_employment: null,
    manager: null,
    linked_user: null,
  };
}

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

describe("/roster/overrides", () => {
  it("creates an override and refreshes the list", async () => {
    const user = userEvent.setup();
    const overrides: RosterOverrideOut[] = [];

    server.use(
      http.get("*/api/v1/hr/employees", () =>
        HttpResponse.json(ok({ items: [employeeRow()], paging: { limit: 12, offset: 0, total: 1 } })),
      ),
      http.get(`*/api/v1/hr/employees/${EMPLOYEE_ID}`, () => HttpResponse.json(ok(employee360()))),
      http.get(`*/api/v1/roster/branches/${BRANCH_ID}/shifts`, () => HttpResponse.json(ok([SHIFT]))),
      http.get(`*/api/v1/roster/employees/${EMPLOYEE_ID}/overrides`, () => HttpResponse.json(ok(overrides))),
      http.put(`*/api/v1/roster/employees/${EMPLOYEE_ID}/overrides/:day`, async ({ params, request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created: RosterOverrideOut = {
          id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
          tenant_id: TENANT_ID,
          employee_id: EMPLOYEE_ID,
          branch_id: BRANCH_ID,
          day: String(params.day),
          override_type: String(body.override_type),
          shift_template_id: body.shift_template_id ? String(body.shift_template_id) : null,
          notes: body.notes ? String(body.notes) : null,
          created_by_user_id: SESSION.user.id,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        };
        overrides.push(created);
        return HttpResponse.json(ok(created));
      }),
    );

    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });
    setSearchParams({ employeeId: EMPLOYEE_ID });

    renderWithProviders(<RosterOverridesPage />);

    await user.click(await screen.findByRole("button", { name: "Create override" }));
    const dialog = await screen.findByRole("dialog");
    await user.clear(within(dialog).getByLabelText("Day"));
    await user.type(within(dialog).getByLabelText("Day"), "2026-01-02");
    await user.selectOptions(within(dialog).getByLabelText("Shift template"), SHIFT_ID);
    await user.click(within(dialog).getByRole("button", { name: "Save override" }));

    const table = await screen.findByRole("table");
    expect(await within(table).findByText("2026-01-02")).toBeVisible();
    expect(await within(table).findByText("SHIFT_CHANGE")).toBeVisible();
  }, 30_000);

  it("routes validation failures through the shared toast handler", async () => {
    const user = userEvent.setup();
    const toastApiErrorMock = vi.mocked(toastApiError);
    toastApiErrorMock.mockReset();

    server.use(
      http.get("*/api/v1/hr/employees", () =>
        HttpResponse.json(ok({ items: [employeeRow()], paging: { limit: 12, offset: 0, total: 1 } })),
      ),
      http.get(`*/api/v1/hr/employees/${EMPLOYEE_ID}`, () => HttpResponse.json(ok(employee360()))),
      http.get(`*/api/v1/roster/branches/${BRANCH_ID}/shifts`, () => HttpResponse.json(ok([SHIFT]))),
      http.get(`*/api/v1/roster/employees/${EMPLOYEE_ID}/overrides`, () => HttpResponse.json(ok([]))),
    );

    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });
    setSearchParams({ employeeId: EMPLOYEE_ID });

    renderWithProviders(<RosterOverridesPage />);

    await user.click(await screen.findByRole("button", { name: "Create override" }));
    const dialog = await screen.findByRole("dialog");
    await user.clear(within(dialog).getByLabelText("Day"));
    await user.click(within(dialog).getByRole("button", { name: "Save override" }));

    await waitFor(() => {
      expect(toastApiErrorMock).toHaveBeenCalledTimes(1);
    });
  });
});
