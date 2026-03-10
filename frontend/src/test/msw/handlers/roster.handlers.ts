import { http, HttpResponse } from "msw";

import { fail, ok } from "@/test/msw/builders/response";

const SHIFT_ID = "10000000-0000-4000-8000-000000000001";
const EMPLOYEE_ID = "20000000-0000-4000-8000-000000000001";
const BRANCH_ID = "30000000-0000-4000-8000-000000000001";

function shift(id = SHIFT_ID) {
  const now = new Date(0).toISOString();
  return {
    id,
    tenant_id: "tenant-1",
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
    created_at: now,
    updated_at: now,
  };
}

function assignment() {
  const now = new Date(0).toISOString();
  return {
    id: "40000000-0000-4000-8000-000000000001",
    tenant_id: "tenant-1",
    employee_id: EMPLOYEE_ID,
    branch_id: BRANCH_ID,
    shift_template_id: SHIFT_ID,
    effective_from: "2026-01-01",
    effective_to: null,
    created_by_user_id: null,
    created_at: now,
    updated_at: now,
  };
}

function override() {
  const now = new Date(0).toISOString();
  return {
    id: "50000000-0000-4000-8000-000000000001",
    tenant_id: "tenant-1",
    employee_id: EMPLOYEE_ID,
    branch_id: BRANCH_ID,
    day: "2026-01-01",
    override_type: "WORKDAY",
    shift_template_id: null,
    notes: null,
    created_by_user_id: null,
    created_at: now,
    updated_at: now,
  };
}

export const rosterHandlers = [
  http.get("*/api/v1/roster/branches/:branchId/shifts", () => HttpResponse.json(ok([]))),

  http.post("*/api/v1/roster/branches/:branchId/shifts", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...shift(),
        code: String(body.code ?? "DAY"),
        name: String(body.name ?? "Day Shift"),
        start_time: String(body.start_time ?? "09:00:00"),
        end_time: String(body.end_time ?? "18:00:00"),
        break_minutes: Number(body.break_minutes ?? 60),
        grace_minutes: Number(body.grace_minutes ?? 10),
        min_full_day_minutes: body.min_full_day_minutes == null ? 480 : Number(body.min_full_day_minutes),
        is_active: body.is_active == null ? true : Boolean(body.is_active),
      }),
    );
  }),

  http.patch("*/api/v1/roster/shifts/:shiftTemplateId", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...shift(String(params.shiftTemplateId)),
        code: String(body.code ?? "DAY"),
        name: String(body.name ?? "Day Shift"),
        start_time: String(body.start_time ?? "09:00:00"),
        end_time: String(body.end_time ?? "18:00:00"),
        break_minutes: body.break_minutes == null ? 60 : Number(body.break_minutes),
        grace_minutes: body.grace_minutes == null ? 10 : Number(body.grace_minutes),
        min_full_day_minutes:
          body.min_full_day_minutes == null ? 480 : Number(body.min_full_day_minutes),
        is_active: body.is_active == null ? true : Boolean(body.is_active),
      }),
    );
  }),

  http.get("*/api/v1/roster/branches/:branchId/default-shift", () =>
    HttpResponse.json(
      fail("roster.default.not_found", "No default shift", {
        correlation_id: "cid-roster-default-not-found",
      }),
      { status: 404 },
    ),
  ),

  http.put("*/api/v1/roster/branches/:branchId/default-shift", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        tenant_id: "tenant-1",
        branch_id: String(params.branchId),
        default_shift_template_id: String(body.shift_template_id ?? SHIFT_ID),
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
      }),
    );
  }),

  http.get("*/api/v1/roster/employees/:employeeId/assignments", () =>
    HttpResponse.json(ok([])),
  ),

  http.post("*/api/v1/roster/employees/:employeeId/assignments", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...assignment(),
        employee_id: String(params.employeeId),
        shift_template_id: String(body.shift_template_id ?? SHIFT_ID),
        effective_from: String(body.effective_from ?? "2026-01-01"),
        effective_to: body.effective_to ? String(body.effective_to) : null,
      }),
    );
  }),

  http.get("*/api/v1/roster/employees/:employeeId/overrides", () =>
    HttpResponse.json(ok([])),
  ),

  http.put("*/api/v1/roster/employees/:employeeId/overrides/:day", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...override(),
        employee_id: String(params.employeeId),
        day: String(params.day),
        override_type: String(body.override_type ?? "WORKDAY"),
        shift_template_id: body.shift_template_id ? String(body.shift_template_id) : null,
        notes: body.notes ? String(body.notes) : null,
      }),
    );
  }),
];
