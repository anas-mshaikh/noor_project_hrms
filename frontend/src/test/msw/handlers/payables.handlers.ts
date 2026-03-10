import { http, HttpResponse } from "msw";

import { ok } from "@/test/msw/builders/response";

function summary(day: string, employeeId = "20000000-0000-4000-8000-000000000001") {
  return {
    day,
    employee_id: employeeId,
    branch_id: "30000000-0000-4000-8000-000000000001",
    shift_template_id: "10000000-0000-4000-8000-000000000001",
    day_type: "WORKDAY",
    presence_status: "PRESENT",
    expected_minutes: 480,
    worked_minutes: 480,
    payable_minutes: 480,
    anomalies_json: null,
    source_breakdown: { source: "assignment" },
    computed_at: new Date(0).toISOString(),
  };
}

export const payablesHandlers = [
  http.get("*/api/v1/attendance/me/payable-days", ({ request }) => {
    const url = new URL(request.url);
    const day = url.searchParams.get("from") ?? "2026-01-01";
    return HttpResponse.json(ok({ items: [summary(day)] }));
  }),

  http.get("*/api/v1/attendance/team/payable-days", ({ request }) => {
    const url = new URL(request.url);
    const day = url.searchParams.get("from") ?? "2026-01-01";
    return HttpResponse.json(ok({ items: [summary(day), summary(day, "20000000-0000-4000-8000-000000000002")] }));
  }),

  http.get("*/api/v1/attendance/admin/payable-days", ({ request }) => {
    const url = new URL(request.url);
    const day = url.searchParams.get("from") ?? "2026-01-01";
    return HttpResponse.json(ok({ items: [summary(day)], next_cursor: null }));
  }),

  http.post("*/api/v1/attendance/payable/recompute", () =>
    HttpResponse.json(ok({ computed_rows: 1 })),
  ),
];
