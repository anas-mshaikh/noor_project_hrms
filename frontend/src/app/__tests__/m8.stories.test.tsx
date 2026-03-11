import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";

import type { EmployeeDirectoryRowOut, HrEmployee360Out, MeResponse } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { setSearchParams } from "@/test/utils/router";
import { seedScope, seedSession } from "@/test/utils/selection";

import PayablesAdminPage from "@/app/payables/admin/page";
import RosterAssignmentsPage from "@/app/roster/assignments/page";
import RosterDefaultPage from "@/app/roster/default/page";
import RosterOverridesPage from "@/app/roster/overrides/page";
import RosterShiftsPage from "@/app/roster/shifts/page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const COMPANY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const BRANCH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const EMPLOYEE_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const SHIFT_ID = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
const DAY = "2026-03-15";

const SESSION: MeResponse = {
  user: { id: "u-hr", email: "hr@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: [
    "roster:shift:read",
    "roster:shift:write",
    "roster:defaults:write",
    "roster:assignment:read",
    "roster:assignment:write",
    "roster:override:read",
    "roster:override:write",
    "attendance:payable:admin:read",
    "attendance:payable:recompute",
    "hr:employee:read",
  ],
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

describe("M8 canonical story", () => {
  it("creates shift/default/assignment/override and recomputes payables", async () => {
    const user = userEvent.setup();
    let shift = null as null | {
      id: string;
      code: string;
      name: string;
      start_time: string;
      end_time: string;
      break_minutes: number;
      grace_minutes: number;
      min_full_day_minutes: number | null;
      expected_minutes: number;
      is_active: boolean;
    };
    let defaultShiftId: string | null = null;
    let assignment: { shift_template_id: string; effective_from: string; effective_to: string | null } | null = null;
    let override: { day: string; override_type: string; shift_template_id: string | null } | null = null;
    let recomputed = false;

    server.use(
      http.get("*/api/v1/hr/employees", () =>
        HttpResponse.json(ok({ items: [employeeRow()], paging: { limit: 12, offset: 0, total: 1 } })),
      ),
      http.get(`*/api/v1/hr/employees/${EMPLOYEE_ID}`, () => HttpResponse.json(ok(employee360()))),
      http.get(`*/api/v1/roster/branches/${BRANCH_ID}/shifts`, () =>
        HttpResponse.json(ok(shift ? [{
          id: shift.id,
          tenant_id: TENANT_ID,
          branch_id: BRANCH_ID,
          code: shift.code,
          name: shift.name,
          start_time: shift.start_time,
          end_time: shift.end_time,
          break_minutes: shift.break_minutes,
          grace_minutes: shift.grace_minutes,
          min_full_day_minutes: shift.min_full_day_minutes,
          is_active: shift.is_active,
          expected_minutes: shift.expected_minutes,
          created_by_user_id: null,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        }] : [])),
      ),
      http.post(`*/api/v1/roster/branches/${BRANCH_ID}/shifts`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        shift = {
          id: SHIFT_ID,
          code: String(body.code),
          name: String(body.name),
          start_time: String(body.start_time),
          end_time: String(body.end_time),
          break_minutes: Number(body.break_minutes ?? 0),
          grace_minutes: Number(body.grace_minutes ?? 0),
          min_full_day_minutes: body.min_full_day_minutes == null ? null : Number(body.min_full_day_minutes),
          expected_minutes: 480,
          is_active: Boolean(body.is_active ?? true),
        };
        return HttpResponse.json(ok({
          id: shift.id,
          tenant_id: TENANT_ID,
          branch_id: BRANCH_ID,
          code: shift.code,
          name: shift.name,
          start_time: shift.start_time,
          end_time: shift.end_time,
          break_minutes: shift.break_minutes,
          grace_minutes: shift.grace_minutes,
          min_full_day_minutes: shift.min_full_day_minutes,
          is_active: shift.is_active,
          expected_minutes: shift.expected_minutes,
          created_by_user_id: null,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        }));
      }),
      http.get(`*/api/v1/roster/branches/${BRANCH_ID}/default-shift`, () => {
        if (!defaultShiftId) {
          return HttpResponse.json({ ok: false, error: { code: "roster.default.not_found", message: "Missing" } }, { status: 404 });
        }
        return HttpResponse.json(ok({
          tenant_id: TENANT_ID,
          branch_id: BRANCH_ID,
          default_shift_template_id: defaultShiftId,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        }));
      }),
      http.put(`*/api/v1/roster/branches/${BRANCH_ID}/default-shift`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        defaultShiftId = String(body.shift_template_id);
        return HttpResponse.json(ok({
          tenant_id: TENANT_ID,
          branch_id: BRANCH_ID,
          default_shift_template_id: defaultShiftId,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        }));
      }),
      http.get(`*/api/v1/roster/employees/${EMPLOYEE_ID}/assignments`, () =>
        HttpResponse.json(ok(assignment ? [{
          id: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
          tenant_id: TENANT_ID,
          employee_id: EMPLOYEE_ID,
          branch_id: BRANCH_ID,
          shift_template_id: assignment.shift_template_id,
          effective_from: assignment.effective_from,
          effective_to: assignment.effective_to,
          created_by_user_id: null,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        }] : [])),
      ),
      http.post(`*/api/v1/roster/employees/${EMPLOYEE_ID}/assignments`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        assignment = {
          shift_template_id: String(body.shift_template_id),
          effective_from: String(body.effective_from),
          effective_to: body.effective_to ? String(body.effective_to) : null,
        };
        return HttpResponse.json(ok({
          id: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
          tenant_id: TENANT_ID,
          employee_id: EMPLOYEE_ID,
          branch_id: BRANCH_ID,
          shift_template_id: assignment.shift_template_id,
          effective_from: assignment.effective_from,
          effective_to: assignment.effective_to,
          created_by_user_id: null,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        }));
      }),
      http.get(`*/api/v1/roster/employees/${EMPLOYEE_ID}/overrides`, () =>
        HttpResponse.json(ok(override ? [{
          id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
          tenant_id: TENANT_ID,
          employee_id: EMPLOYEE_ID,
          branch_id: BRANCH_ID,
          day: override.day,
          override_type: override.override_type,
          shift_template_id: override.shift_template_id,
          notes: null,
          created_by_user_id: null,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        }] : [])),
      ),
      http.put(`*/api/v1/roster/employees/${EMPLOYEE_ID}/overrides/:day`, async ({ params, request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        override = {
          day: String(params.day),
          override_type: String(body.override_type),
          shift_template_id: body.shift_template_id ? String(body.shift_template_id) : null,
        };
        return HttpResponse.json(ok({
          id: "ffffffff-ffff-4fff-8fff-ffffffffffff",
          tenant_id: TENANT_ID,
          employee_id: EMPLOYEE_ID,
          branch_id: BRANCH_ID,
          day: override.day,
          override_type: override.override_type,
          shift_template_id: override.shift_template_id,
          notes: null,
          created_by_user_id: null,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
        }));
      }),
      http.get("*/api/v1/attendance/admin/payable-days", () =>
        HttpResponse.json(ok({
          items: recomputed ? [{
            day: DAY,
            employee_id: EMPLOYEE_ID,
            branch_id: BRANCH_ID,
            shift_template_id: override?.shift_template_id ?? assignment?.shift_template_id ?? defaultShiftId,
            day_type: override?.override_type === "WORKDAY" ? "WORKDAY" : "WEEKOFF",
            presence_status: "PRESENT",
            expected_minutes: 480,
            worked_minutes: 480,
            payable_minutes: 480,
            anomalies_json: null,
            source_breakdown: { default_shift: defaultShiftId, assignment: assignment?.shift_template_id ?? null, override: override?.override_type ?? null },
            computed_at: new Date(0).toISOString(),
          }] : [],
          next_cursor: null,
        })),
      ),
      http.post("*/api/v1/attendance/payable/recompute", () => {
        recomputed = true;
        return HttpResponse.json(ok({ computed_rows: 1 }));
      }),
    );

    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });

    let view = renderWithProviders(<RosterShiftsPage />);
    await user.click(await screen.findByRole("button", { name: "Create shift" }));
    let dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Code"), "DAY");
    await user.type(within(dialog).getByLabelText("Name"), "Day Shift");
    await user.click(within(dialog).getByRole("button", { name: "Create shift" }));
    let table = await screen.findByRole("table");
    expect(await within(table).findByText("Day Shift")).toBeVisible();
    view.unmount();

    view = renderWithProviders(<RosterDefaultPage />);
    await user.click((await screen.findAllByRole("button", { name: "Set default shift" }))[0]);
    dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Shift template"), SHIFT_ID);
    await user.click(within(dialog).getByRole("button", { name: "Save default" }));
    expect(await screen.findByText("Day Shift")).toBeVisible();
    expect(await screen.findByText("DAY")).toBeVisible();
    view.unmount();

    setSearchParams({ employeeId: EMPLOYEE_ID });
    view = renderWithProviders(<RosterAssignmentsPage />);
    await user.click(await screen.findByRole("button", { name: "Create assignment" }));
    dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Shift template"), SHIFT_ID);
    await user.type(within(dialog).getByLabelText("Effective from"), "2026-01-01");
    await user.click(within(dialog).getByRole("button", { name: "Create assignment" }));
    table = await screen.findByRole("table");
    expect(await within(table).findByText("2026-01-01")).toBeVisible();
    expect(await within(table).findByText("Day Shift")).toBeVisible();
    view.unmount();

    setSearchParams({ employeeId: EMPLOYEE_ID });
    view = renderWithProviders(<RosterOverridesPage />);
    await user.click(await screen.findByRole("button", { name: "Create override" }));
    dialog = await screen.findByRole("dialog");
    await user.clear(within(dialog).getByLabelText("Day"));
    await user.type(within(dialog).getByLabelText("Day"), DAY);
    await user.click(within(dialog).getByRole("button", { name: "Save override" }));
    table = await screen.findByRole("table");
    expect(await within(table).findByText(DAY)).toBeVisible();
    expect(await within(table).findByText("SHIFT_CHANGE")).toBeVisible();
    view.unmount();

    view = renderWithProviders(<PayablesAdminPage />);
    await user.clear(screen.getByLabelText("From"));
    await user.type(screen.getByLabelText("From"), DAY);
    await user.clear(screen.getByLabelText("To"));
    await user.type(screen.getByLabelText("To"), DAY);
    await user.click(await screen.findByRole("button", { name: "Recompute" }));
    table = await screen.findByRole("table");
    expect(await within(table).findByText(DAY)).toBeVisible();
    expect(await within(table).findByText("WEEKOFF")).toBeVisible();
    view.unmount();
  }, 45_000);
});
