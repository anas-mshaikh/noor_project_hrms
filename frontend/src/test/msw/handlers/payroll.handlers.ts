import { http, HttpResponse } from "msw";

import { ok } from "@/test/msw/builders/response";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const CALENDAR_ID = "11111111-1111-4111-8111-111111111111";
const PERIOD_ID = "22222222-2222-4222-8222-222222222222";
const COMPONENT_ID = "33333333-3333-4333-8333-333333333333";
const STRUCTURE_ID = "44444444-4444-4444-8444-444444444444";
const LINE_ID = "55555555-5555-4555-8555-555555555555";
const EMPLOYEE_ID = "66666666-6666-4666-8666-666666666666";
const PAYRUN_ID = "77777777-7777-4777-8777-777777777777";
const PAYRUN_ITEM_ID = "88888888-8888-4888-8888-888888888888";
const PAYSLIP_ID = "99999999-9999-4999-8999-999999999999";
const BRANCH_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const WORKFLOW_REQUEST_ID = "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee";
const now = new Date(0).toISOString();

function calendar() {
  return {
    id: CALENDAR_ID,
    tenant_id: TENANT_ID,
    code: "MONTHLY",
    name: "Monthly Payroll",
    frequency: "MONTHLY",
    currency_code: "SAR",
    timezone: "Asia/Riyadh",
    is_active: true,
    created_by_user_id: null,
    created_at: now,
    updated_at: now,
  };
}

function period() {
  return {
    id: PERIOD_ID,
    tenant_id: TENANT_ID,
    calendar_id: CALENDAR_ID,
    period_key: "2026-03",
    start_date: "2026-03-01",
    end_date: "2026-03-31",
    status: "OPEN",
    created_at: now,
    updated_at: now,
  };
}

function component() {
  return {
    id: COMPONENT_ID,
    tenant_id: TENANT_ID,
    code: "BASIC",
    name: "Basic Salary",
    component_type: "EARNING",
    calc_mode: "FIXED",
    default_amount: "5000.00",
    default_percent: null,
    is_taxable: false,
    is_active: true,
    created_at: now,
    updated_at: now,
  };
}

function structure() {
  return {
    id: STRUCTURE_ID,
    tenant_id: TENANT_ID,
    code: "STD",
    name: "Standard Structure",
    is_active: true,
    created_at: now,
    updated_at: now,
  };
}

function line() {
  return {
    id: LINE_ID,
    tenant_id: TENANT_ID,
    salary_structure_id: STRUCTURE_ID,
    component_id: COMPONENT_ID,
    sort_order: 10,
    calc_mode_override: null,
    amount_override: null,
    percent_override: null,
    created_at: now,
  };
}

function compensation() {
  return {
    id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    tenant_id: TENANT_ID,
    employee_id: EMPLOYEE_ID,
    currency_code: "SAR",
    salary_structure_id: STRUCTURE_ID,
    base_amount: "5000.00",
    effective_from: "2026-03-01",
    effective_to: null,
    overrides_json: null,
    created_by_user_id: null,
    created_at: now,
    updated_at: now,
  };
}

function payrun(status = "DRAFT") {
  return {
    id: PAYRUN_ID,
    tenant_id: TENANT_ID,
    calendar_id: CALENDAR_ID,
    period_id: PERIOD_ID,
    branch_id: BRANCH_ID,
    version: 1,
    status,
    generated_at: now,
    generated_by_user_id: null,
    workflow_request_id: status === "PENDING_APPROVAL" || status === "APPROVED" || status === "PUBLISHED" ? WORKFLOW_REQUEST_ID : null,
    idempotency_key: "payrun:test",
    totals_json: {
      included_count: 1,
      excluded_count: 0,
      gross_total: "5000.00",
      deductions_total: "0.00",
      net_total: "5000.00",
      currency_code: "SAR",
      computed_at: now,
    },
    created_at: now,
    updated_at: now,
  };
}

function payrunItem(status = "INCLUDED") {
  return {
    id: PAYRUN_ITEM_ID,
    tenant_id: TENANT_ID,
    payrun_id: PAYRUN_ID,
    employee_id: EMPLOYEE_ID,
    payable_days: 31,
    payable_minutes: 14880,
    working_days_in_period: 31,
    gross_amount: "5000.00",
    deductions_amount: "0.00",
    net_amount: "5000.00",
    status,
    computed_json: { base_amount: "5000.00" },
    anomalies_json: status === "EXCLUDED" ? { NO_COMPENSATION: true } : null,
    created_at: now,
  };
}

function payrunLine() {
  return {
    id: "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
    tenant_id: TENANT_ID,
    payrun_item_id: PAYRUN_ITEM_ID,
    component_id: COMPONENT_ID,
    component_code: "BASIC",
    component_type: "EARNING",
    amount: "5000.00",
    meta_json: null,
    created_at: now,
  };
}

function payslip() {
  return {
    id: PAYSLIP_ID,
    tenant_id: TENANT_ID,
    payrun_id: PAYRUN_ID,
    employee_id: EMPLOYEE_ID,
    status: "PUBLISHED",
    dms_document_id: "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
    period_key: "2026-03",
    created_at: now,
    updated_at: now,
  };
}

export const payrollHandlers = [
  http.get("*/api/v1/payroll/calendars", () => HttpResponse.json(ok([calendar()]))),
  http.post("*/api/v1/payroll/calendars", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...calendar(),
        id: "f1111111-1111-4111-8111-111111111111",
        code: String(body.code ?? "MONTHLY"),
        name: String(body.name ?? "Monthly Payroll"),
        currency_code: String(body.currency_code ?? "SAR"),
        timezone: String(body.timezone ?? "Asia/Riyadh"),
        is_active: body.is_active == null ? true : Boolean(body.is_active),
      }),
    );
  }),

  http.get("*/api/v1/payroll/calendars/:calendarId/periods", () =>
    HttpResponse.json(ok([period()])),
  ),
  http.post("*/api/v1/payroll/calendars/:calendarId/periods", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...period(),
        id: "f2222222-2222-4222-8222-222222222222",
        calendar_id: String(params.calendarId),
        period_key: String(body.period_key ?? "2026-03"),
        start_date: String(body.start_date ?? "2026-03-01"),
        end_date: String(body.end_date ?? "2026-03-31"),
      }),
    );
  }),

  http.get("*/api/v1/payroll/components", () => HttpResponse.json(ok([component()]))),
  http.post("*/api/v1/payroll/components", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...component(),
        id: "f3333333-3333-4333-8333-333333333333",
        code: String(body.code ?? "BASIC"),
        name: String(body.name ?? "Basic Salary"),
        component_type: String(body.component_type ?? "EARNING"),
        calc_mode: String(body.calc_mode ?? "FIXED"),
        default_amount: body.default_amount == null ? null : String(body.default_amount),
        default_percent: body.default_percent == null ? null : String(body.default_percent),
        is_taxable: body.is_taxable == null ? false : Boolean(body.is_taxable),
        is_active: body.is_active == null ? true : Boolean(body.is_active),
      }),
    );
  }),

  http.post("*/api/v1/payroll/salary-structures", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...structure(),
        id: "f4444444-4444-4444-8444-444444444444",
        code: String(body.code ?? "STD"),
        name: String(body.name ?? "Standard Structure"),
        is_active: body.is_active == null ? true : Boolean(body.is_active),
      }),
    );
  }),
  http.get("*/api/v1/payroll/salary-structures/:structureId", ({ params }) =>
    HttpResponse.json(
      ok({
        structure: { ...structure(), id: String(params.structureId) },
        lines: [line()],
      }),
    ),
  ),
  http.post("*/api/v1/payroll/salary-structures/:structureId/lines", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...line(),
        id: "f5555555-5555-4555-8555-555555555555",
        salary_structure_id: String(params.structureId),
        component_id: String(body.component_id ?? COMPONENT_ID),
        sort_order: Number(body.sort_order ?? 10),
        calc_mode_override: body.calc_mode_override == null ? null : String(body.calc_mode_override),
        amount_override: body.amount_override == null ? null : String(body.amount_override),
        percent_override: body.percent_override == null ? null : String(body.percent_override),
      }),
    );
  }),

  http.get("*/api/v1/payroll/employees/:employeeId/compensation", ({ params }) =>
    HttpResponse.json(ok([{ ...compensation(), employee_id: String(params.employeeId) }])),
  ),
  http.post("*/api/v1/payroll/employees/:employeeId/compensation", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...compensation(),
        id: "f6666666-6666-4666-8666-666666666666",
        employee_id: String(params.employeeId),
        currency_code: String(body.currency_code ?? "SAR"),
        salary_structure_id: String(body.salary_structure_id ?? STRUCTURE_ID),
        base_amount: String(body.base_amount ?? "5000.00"),
        effective_from: String(body.effective_from ?? "2026-03-01"),
        effective_to: body.effective_to ? String(body.effective_to) : null,
        overrides_json: (body.overrides_json as Record<string, unknown> | null | undefined) ?? null,
      }),
    );
  }),

  http.post("*/api/v1/payroll/payruns/generate", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...payrun("DRAFT"),
        calendar_id: String(body.calendar_id ?? CALENDAR_ID),
        branch_id: body.branch_id ? String(body.branch_id) : BRANCH_ID,
        idempotency_key: String(body.idempotency_key ?? "payrun:test"),
      }),
    );
  }),
  http.get("*/api/v1/payroll/payruns/:payrunId", ({ request, params }) => {
    const url = new URL(request.url);
    const includeLines = url.searchParams.get("include_lines") === "1";
    return HttpResponse.json(
      ok({
        payrun: { ...payrun("DRAFT"), id: String(params.payrunId) },
        items: [payrunItem()],
        lines: includeLines ? [payrunLine()] : null,
      }),
    );
  }),
  http.post("*/api/v1/payroll/payruns/:payrunId/submit-approval", ({ params }) =>
    HttpResponse.json(
      ok({
        payrun_id: String(params.payrunId),
        workflow_request_id: WORKFLOW_REQUEST_ID,
        status: "PENDING_APPROVAL",
      }),
    ),
  ),
  http.post("*/api/v1/payroll/payruns/:payrunId/publish", ({ params }) =>
    HttpResponse.json(
      ok({
        payrun_id: String(params.payrunId),
        published_count: 1,
        status: "PUBLISHED",
      }),
    ),
  ),
  http.get("*/api/v1/payroll/payruns/:payrunId/export", () =>
    new HttpResponse("employee_id,net_amount\n66666666-6666-4666-8666-666666666666,5000.00\n", {
      status: 200,
      headers: {
        "Content-Type": "text/csv",
        "Content-Disposition": 'attachment; filename="payrun.csv"',
      },
    }),
  ),

  http.get("*/api/v1/ess/me/payslips", () => HttpResponse.json(ok({ items: [payslip()] }))),
  http.get("*/api/v1/ess/me/payslips/:payslipId", ({ params }) =>
    HttpResponse.json(ok({ ...payslip(), id: String(params.payslipId) })),
  ),
  http.get("*/api/v1/ess/me/payslips/:payslipId/download", ({ params }) =>
    new HttpResponse(
      JSON.stringify({ payslip_id: String(params.payslipId), period_key: "2026-03", totals: { net_amount: "5000.00" } }),
      {
        status: 200,
        headers: {
          "Content-Type": "application/json",
          "Content-Disposition": 'attachment; filename="payslip_2026-03.json"',
        },
      },
    ),
  ),
];
