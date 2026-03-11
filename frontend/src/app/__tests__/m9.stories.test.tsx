import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";

import type {
  EmployeeCompensationOut,
  EmployeeDirectoryListOut,
  HrEmployee360Out,
  MeResponse,
  PayrollCalendarOut,
  PayrollComponentOut,
  PayrollPeriodOut,
  SalaryStructureLineOut,
  WorkflowRequestDetailOut,
} from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { setParams, setPathname, setSearchParams } from "@/test/utils/router";
import { seedScope, seedSession } from "@/test/utils/selection";

import EssPayslipsPage from "@/app/ess/payslips/page";
import PayrollCalendarsPage from "@/app/payroll/calendars/page";
import PayrollComponentsPage from "@/app/payroll/components/page";
import PayrollCompensationPage from "@/app/payroll/compensation/page";
import PayrollPayrunDetailPage from "@/app/payroll/payruns/[payrunId]/page";
import PayrollPayrunsPage from "@/app/payroll/payruns/page";
import PayrollStructureDetailPage from "@/app/payroll/structures/[structureId]/page";
import PayrollStructuresPage from "@/app/payroll/structures/page";
import WorkflowRequestDeepLinkPage from "@/app/workflow/requests/[requestId]/page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const COMPANY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const BRANCH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const CALENDAR_ID = "11111111-1111-4111-8111-111111111111";
const PERIOD_ID = "22222222-2222-4222-8222-222222222222";
const COMPONENT_ID = "33333333-3333-4333-8333-333333333333";
const STRUCTURE_ID = "44444444-4444-4444-8444-444444444444";
const EMPLOYEE_ID = "55555555-5555-4555-8555-555555555555";
const PAYRUN_ID = "66666666-6666-4666-8666-666666666666";
const WORKFLOW_REQUEST_ID = "77777777-7777-4777-8777-777777777777";
const PAYSLIP_ID = "88888888-8888-4888-8888-888888888888";

const SESSION: MeResponse = {
  user: { id: "u-payroll", email: "payroll@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: [
    "payroll:calendar:read",
    "payroll:calendar:write",
    "payroll:component:read",
    "payroll:component:write",
    "payroll:structure:read",
    "payroll:structure:write",
    "payroll:compensation:read",
    "payroll:compensation:write",
    "payroll:payrun:read",
    "payroll:payrun:generate",
    "payroll:payrun:submit",
    "payroll:payrun:publish",
    "workflow:request:read",
    "workflow:request:approve",
    "payroll:payslip:read",
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

function employeeList(): EmployeeDirectoryListOut {
  return {
    items: [
      {
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
      },
    ],
    paging: { limit: 8, offset: 0, total: 1 },
  };
}

function employee360(): HrEmployee360Out {
  const now = new Date(0).toISOString();
  return {
    employee: {
      id: EMPLOYEE_ID,
      tenant_id: TENANT_ID,
      company_id: COMPANY_ID,
      person_id: "person-1",
      employee_code: "E0001",
      status: "ACTIVE",
      join_date: "2026-01-01",
      termination_date: null,
      created_at: now,
      updated_at: now,
    },
    person: {
      id: "person-1",
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
    current_employment: {
      id: "employment-1",
      tenant_id: TENANT_ID,
      employee_id: EMPLOYEE_ID,
      company_id: COMPANY_ID,
      branch_id: BRANCH_ID,
      org_unit_id: null,
      job_title_id: null,
      grade_id: null,
      manager_employee_id: null,
      start_date: "2026-01-01",
      end_date: null,
      is_primary: true,
      created_at: now,
      updated_at: now,
    },
    manager: null,
    linked_user: null,
  };
}

describe("M9 golden flow", () => {
  it("creates payroll setup, generates a payrun, approves it, publishes it, and exposes a payslip", async () => {
    const user = userEvent.setup();
    const now = new Date(0).toISOString();
    const calendars: PayrollCalendarOut[] = [];
    const periods: PayrollPeriodOut[] = [];
    const components: PayrollComponentOut[] = [];
    const lines: SalaryStructureLineOut[] = [];
    const compensation: EmployeeCompensationOut[] = [];
    let payrunStatus: "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "PUBLISHED" | null = null;
    let workflowStatus: "PENDING" | "APPROVED" = "PENDING";

    server.use(
      http.get("*/api/v1/payroll/calendars", () => HttpResponse.json(ok(calendars))),
      http.post("*/api/v1/payroll/calendars", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created: PayrollCalendarOut = {
          id: CALENDAR_ID,
          tenant_id: TENANT_ID,
          code: String(body.code ?? "MONTHLY"),
          name: String(body.name ?? "Monthly Payroll"),
          frequency: "MONTHLY",
          currency_code: String(body.currency_code ?? "SAR"),
          timezone: String(body.timezone ?? "Asia/Riyadh"),
          is_active: true,
          created_by_user_id: null,
          created_at: now,
          updated_at: now,
        };
        calendars.splice(0, calendars.length, created);
        return HttpResponse.json(ok(created));
      }),
      http.get(`*/api/v1/payroll/calendars/${CALENDAR_ID}/periods`, () => HttpResponse.json(ok(periods))),
      http.post(`*/api/v1/payroll/calendars/${CALENDAR_ID}/periods`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created: PayrollPeriodOut = {
          id: PERIOD_ID,
          tenant_id: TENANT_ID,
          calendar_id: CALENDAR_ID,
          period_key: String(body.period_key ?? "2026-03"),
          start_date: String(body.start_date ?? "2026-03-01"),
          end_date: String(body.end_date ?? "2026-03-31"),
          status: "OPEN",
          created_at: now,
          updated_at: now,
        };
        periods.splice(0, periods.length, created);
        return HttpResponse.json(ok(created));
      }),
      http.get("*/api/v1/payroll/components", () => HttpResponse.json(ok(components))),
      http.post("*/api/v1/payroll/components", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created: PayrollComponentOut = {
          id: COMPONENT_ID,
          tenant_id: TENANT_ID,
          code: String(body.code ?? "BASIC"),
          name: String(body.name ?? "Basic Salary"),
          component_type: "EARNING",
          calc_mode: "FIXED",
          default_amount: "5000.00",
          default_percent: null,
          is_taxable: false,
          is_active: true,
          created_at: now,
          updated_at: now,
        };
        components.splice(0, components.length, created);
        return HttpResponse.json(ok(created));
      }),
      http.post("*/api/v1/payroll/salary-structures", async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(
          ok({
            id: STRUCTURE_ID,
            tenant_id: TENANT_ID,
            code: String(body.code ?? "STD"),
            name: String(body.name ?? "Standard Structure"),
            is_active: true,
            created_at: now,
            updated_at: now,
          }),
        );
      }),
      http.get(`*/api/v1/payroll/salary-structures/${STRUCTURE_ID}`, () =>
        HttpResponse.json(
          ok({
            structure: {
              id: STRUCTURE_ID,
              tenant_id: TENANT_ID,
              code: "STD",
              name: "Standard Structure",
              is_active: true,
              created_at: now,
              updated_at: now,
            },
            lines,
          }),
        ),
      ),
      http.post(`*/api/v1/payroll/salary-structures/${STRUCTURE_ID}/lines`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created: SalaryStructureLineOut = {
          id: "line-1",
          tenant_id: TENANT_ID,
          salary_structure_id: STRUCTURE_ID,
          component_id: String(body.component_id ?? COMPONENT_ID),
          sort_order: Number(body.sort_order ?? 10),
          calc_mode_override: null,
          amount_override: null,
          percent_override: null,
          created_at: now,
        };
        lines.splice(0, lines.length, created);
        return HttpResponse.json(ok(created));
      }),
      http.get("*/api/v1/hr/employees", () => HttpResponse.json(ok(employeeList()))),
      http.get(`*/api/v1/hr/employees/${EMPLOYEE_ID}`, () => HttpResponse.json(ok(employee360()))),
      http.get(`*/api/v1/payroll/employees/${EMPLOYEE_ID}/compensation`, () =>
        HttpResponse.json(ok(compensation)),
      ),
      http.post(`*/api/v1/payroll/employees/${EMPLOYEE_ID}/compensation`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created: EmployeeCompensationOut = {
          id: "comp-1",
          tenant_id: TENANT_ID,
          employee_id: EMPLOYEE_ID,
          currency_code: String(body.currency_code ?? "SAR"),
          salary_structure_id: String(body.salary_structure_id ?? STRUCTURE_ID),
          base_amount: String(body.base_amount ?? "5000.00"),
          effective_from: String(body.effective_from ?? "2026-03-01"),
          effective_to: null,
          overrides_json: null,
          created_by_user_id: null,
          created_at: now,
          updated_at: now,
        };
        compensation.splice(0, compensation.length, created);
        return HttpResponse.json(ok(created));
      }),
      http.post("*/api/v1/payroll/payruns/generate", () => {
        payrunStatus = "DRAFT";
        return HttpResponse.json(
          ok({
            id: PAYRUN_ID,
            tenant_id: TENANT_ID,
            calendar_id: CALENDAR_ID,
            period_id: PERIOD_ID,
            branch_id: BRANCH_ID,
            version: 1,
            status: payrunStatus,
            generated_at: now,
            generated_by_user_id: null,
            workflow_request_id: null,
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
          }),
        );
      }),
      http.get(`*/api/v1/payroll/payruns/${PAYRUN_ID}`, () => {
        const status = payrunStatus ?? "DRAFT";
        return HttpResponse.json(
          ok({
            payrun: {
              id: PAYRUN_ID,
              tenant_id: TENANT_ID,
              calendar_id: CALENDAR_ID,
              period_id: PERIOD_ID,
              branch_id: BRANCH_ID,
              version: 1,
              status,
              generated_at: now,
              generated_by_user_id: null,
              workflow_request_id: status === "DRAFT" ? null : WORKFLOW_REQUEST_ID,
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
            },
            items: [
              {
                id: "item-1",
                tenant_id: TENANT_ID,
                payrun_id: PAYRUN_ID,
                employee_id: EMPLOYEE_ID,
                payable_days: 31,
                payable_minutes: 14880,
                working_days_in_period: 31,
                gross_amount: "5000.00",
                deductions_amount: "0.00",
                net_amount: "5000.00",
                status: "INCLUDED",
                computed_json: { base_amount: "5000.00" },
                anomalies_json: null,
                created_at: now,
              },
            ],
            lines: [
              {
                id: "line-payrun-1",
                tenant_id: TENANT_ID,
                payrun_item_id: "item-1",
                component_id: COMPONENT_ID,
                component_code: "BASIC",
                component_type: "EARNING",
                amount: "5000.00",
                meta_json: null,
                created_at: now,
              },
            ],
          }),
        );
      }),
      http.post(`*/api/v1/payroll/payruns/${PAYRUN_ID}/submit-approval`, () => {
        payrunStatus = "PENDING_APPROVAL";
        workflowStatus = "PENDING";
        return HttpResponse.json(
          ok({ payrun_id: PAYRUN_ID, workflow_request_id: WORKFLOW_REQUEST_ID, status: payrunStatus }),
        );
      }),
      http.get(`*/api/v1/workflow/requests/${WORKFLOW_REQUEST_ID}`, () => {
        const detail: WorkflowRequestDetailOut = {
          request: {
            id: WORKFLOW_REQUEST_ID,
            request_type_code: "PAYRUN_APPROVAL",
            status: workflowStatus,
            current_step: 0,
            subject: "Approve March payroll",
            payload: { payrun_id: PAYRUN_ID, period_key: "2026-03", branch_id: BRANCH_ID },
            tenant_id: TENANT_ID,
            company_id: COMPANY_ID,
            branch_id: BRANCH_ID,
            created_by_user_id: SESSION.user.id,
            requester_employee_id: EMPLOYEE_ID,
            subject_employee_id: null,
            entity_type: "payroll.payrun",
            entity_id: PAYRUN_ID,
            created_at: now,
            updated_at: now,
          },
          steps: [],
          comments: [],
          attachments: [],
          events: [],
        };
        return HttpResponse.json(ok(detail));
      }),
      http.post(`*/api/v1/workflow/requests/${WORKFLOW_REQUEST_ID}/approve`, () => {
        workflowStatus = "APPROVED";
        payrunStatus = "APPROVED";
        return HttpResponse.json(ok({ id: WORKFLOW_REQUEST_ID, status: "APPROVED", current_step: 0 }));
      }),
      http.post(`*/api/v1/payroll/payruns/${PAYRUN_ID}/publish`, () => {
        payrunStatus = "PUBLISHED";
        return HttpResponse.json(ok({ payrun_id: PAYRUN_ID, published_count: 1, status: payrunStatus }));
      }),
      http.get("*/api/v1/ess/me/payslips", () =>
        HttpResponse.json(
          ok({
            items:
              payrunStatus === "PUBLISHED"
                ? [
                    {
                      id: PAYSLIP_ID,
                      tenant_id: TENANT_ID,
                      payrun_id: PAYRUN_ID,
                      employee_id: EMPLOYEE_ID,
                      status: "PUBLISHED",
                      dms_document_id: "doc-1",
                      period_key: "2026-03",
                      created_at: now,
                      updated_at: now,
                    },
                  ]
                : [],
          }),
        ),
      ),
    );

    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });

    let view = renderWithProviders(<PayrollCalendarsPage />);
    await user.click(await screen.findByRole("button", { name: "Create calendar" }));
    let dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Code"), "MONTHLY");
    await user.type(within(dialog).getByLabelText("Name"), "Monthly Payroll");
    await user.click(within(dialog).getByRole("button", { name: "Create calendar" }));
    await user.click(await screen.findByRole("button", { name: "Create period" }));
    dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Period key"), "2026-03");
    await user.type(within(dialog).getByLabelText("Start date"), "2026-03-01");
    await user.type(within(dialog).getByLabelText("End date"), "2026-03-31");
    await user.click(within(dialog).getByRole("button", { name: "Create period" }));
    expect(await screen.findByRole("cell", { name: "2026-03" })).toBeVisible();
    view.unmount();

    view = renderWithProviders(<PayrollComponentsPage />);
    await user.click(await screen.findByRole("button", { name: "Create component" }));
    dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Code"), "BASIC");
    await user.type(within(dialog).getByLabelText("Name"), "Basic Salary");
    await user.click(within(dialog).getByRole("button", { name: "Create component" }));
    expect(await screen.findByRole("cell", { name: "Basic Salary" })).toBeVisible();
    view.unmount();

    view = renderWithProviders(<PayrollStructuresPage />);
    await user.click(await screen.findByRole("button", { name: "Create structure" }));
    dialog = await screen.findByRole("dialog");
    await user.type(within(dialog).getByLabelText("Code"), "STD");
    await user.type(within(dialog).getByLabelText("Name"), "Standard Structure");
    await user.click(within(dialog).getByRole("button", { name: "Create structure" }));
    view.unmount();

    setPathname(`/payroll/structures/${STRUCTURE_ID}`);
    setParams({ structureId: STRUCTURE_ID });
    view = renderWithProviders(<PayrollStructureDetailPage params={{ structureId: STRUCTURE_ID }} />);
    await user.click(await screen.findByRole("button", { name: "Add line" }));
    dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Component"), COMPONENT_ID);
    await user.clear(within(dialog).getByLabelText("Sort order"));
    await user.type(within(dialog).getByLabelText("Sort order"), "10");
    await user.click(within(dialog).getByRole("button", { name: "Add line" }));
    let table = await screen.findByRole("table");
    expect(await within(table).findByText("Basic Salary")).toBeVisible();
    expect(await within(table).findByText("BASIC")).toBeVisible();
    view.unmount();

    setSearchParams({ employeeId: EMPLOYEE_ID, structureId: STRUCTURE_ID });
    view = renderWithProviders(<PayrollCompensationPage />);
    await user.click(await screen.findByRole("button", { name: "Add compensation record" }));
    dialog = await screen.findByRole("dialog");
    await user.clear(within(dialog).getByLabelText("Base amount"));
    await user.type(within(dialog).getByLabelText("Base amount"), "5000.00");
    await user.clear(within(dialog).getByLabelText("Effective from"));
    await user.type(within(dialog).getByLabelText("Effective from"), "2026-03-01");
    await user.click(within(dialog).getByRole("button", { name: "Add compensation record" }));
    expect(await screen.findByText("SAR 5,000.00")).toBeVisible();
    view.unmount();

    view = renderWithProviders(<PayrollPayrunsPage />);
    await user.click(await screen.findByRole("button", { name: "Generate payrun" }));
    dialog = await screen.findByRole("dialog");
    await user.selectOptions(within(dialog).getByLabelText("Calendar"), CALENDAR_ID);
    await user.selectOptions(within(dialog).getByLabelText("Period"), "2026-03");
    await user.click(within(dialog).getByRole("button", { name: "Generate payrun" }));
    view.unmount();

    setPathname(`/payroll/payruns/${PAYRUN_ID}`);
    setParams({ payrunId: PAYRUN_ID });
    view = renderWithProviders(<PayrollPayrunDetailPage params={{ payrunId: PAYRUN_ID }} />);
    await user.click(await screen.findByRole("button", { name: "Submit for approval" }));
    expect(await screen.findByRole("link", { name: "Open approval request" })).toHaveAttribute(
      "href",
      `/workflow/requests/${WORKFLOW_REQUEST_ID}`,
    );
    view.unmount();

    setPathname(`/workflow/requests/${WORKFLOW_REQUEST_ID}`);
    setParams({ requestId: WORKFLOW_REQUEST_ID });
    setSearchParams({});
    view = renderWithProviders(
      <WorkflowRequestDeepLinkPage params={{ requestId: WORKFLOW_REQUEST_ID }} />,
    );
    await user.click(await screen.findByRole("button", { name: "Approve" }));
    expect(await screen.findByText("APPROVED")).toBeVisible();
    view.unmount();

    setPathname(`/payroll/payruns/${PAYRUN_ID}`);
    setParams({ payrunId: PAYRUN_ID });
    view = renderWithProviders(<PayrollPayrunDetailPage params={{ payrunId: PAYRUN_ID }} />);
    await user.click(await screen.findByRole("button", { name: "Publish" }));
    expect(await screen.findByText("Status Published")).toBeVisible();
    view.unmount();

    setSearchParams({ year: 2026, payslipId: PAYSLIP_ID });
    view = renderWithProviders(<EssPayslipsPage />);
    table = await screen.findByRole("table");
    expect(await within(table).findByText("2026-03")).toBeVisible();
    expect(screen.getByRole("button", { name: "Download payslip" })).toBeVisible();
    view.unmount();
  }, 90_000);
});
