import { describe, expect, it } from "vitest";
import { fireEvent, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import type {
  EmployeeCompensationOut,
  EmployeeDirectoryListOut,
  HrEmployee360Out,
  MeResponse,
} from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { setSearchParams } from "@/test/utils/router";
import { clearScope, seedScope, seedSession } from "@/test/utils/selection";

import PayrollCompensationPage from "../page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const COMPANY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const BRANCH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const EMPLOYEE_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";
const STRUCTURE_ID = "44444444-4444-4444-8444-444444444444";
const SESSION: MeResponse = {
  user: { id: "u-payroll", email: "payroll@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: [
    "payroll:compensation:read",
    "payroll:compensation:write",
    "payroll:structure:read",
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

function compensation(baseAmount = "5000.00"): EmployeeCompensationOut {
  const now = new Date(0).toISOString();
  return {
    id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    tenant_id: TENANT_ID,
    employee_id: EMPLOYEE_ID,
    currency_code: "SAR",
    salary_structure_id: STRUCTURE_ID,
    base_amount: baseAmount,
    effective_from: "2026-03-01",
    effective_to: null,
    overrides_json: null,
    created_by_user_id: null,
    created_at: now,
    updated_at: now,
  };
}

describe("/payroll/compensation", () => {
  it("fails closed without a selected company", async () => {
    seedSession(SESSION);
    clearScope();
    setSearchParams({});

    renderWithProviders(<PayrollCompensationPage />);

    expect(await screen.findByText("Select a company")).toBeVisible();
  });

  it("loads compensation history and adds a record", async () => {
    const records: EmployeeCompensationOut[] = [];

    server.use(
      http.get("*/api/v1/hr/employees", () => HttpResponse.json(ok(employeeList()))),
      http.get(`*/api/v1/hr/employees/${EMPLOYEE_ID}`, () => HttpResponse.json(ok(employee360()))),
      http.get(`*/api/v1/payroll/employees/${EMPLOYEE_ID}/compensation`, () =>
        HttpResponse.json(ok(records)),
      ),
      http.get(`*/api/v1/payroll/salary-structures/${STRUCTURE_ID}`, () =>
        HttpResponse.json(
          ok({
            structure: {
              id: STRUCTURE_ID,
              tenant_id: TENANT_ID,
              code: "STD",
              name: "Standard Structure",
              is_active: true,
              created_at: new Date(0).toISOString(),
              updated_at: new Date(0).toISOString(),
            },
            lines: [],
          }),
        ),
      ),
      http.post(`*/api/v1/payroll/employees/${EMPLOYEE_ID}/compensation`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created = compensation(String(body.base_amount ?? "5000.00"));
        records.push(created);
        return HttpResponse.json(ok(created));
      }),
    );

    seedSession(SESSION);
    seedScope({ tenantId: TENANT_ID, companyId: COMPANY_ID, branchId: BRANCH_ID });
    setSearchParams({ employeeId: EMPLOYEE_ID, structureId: STRUCTURE_ID });

    renderWithProviders(<PayrollCompensationPage />);

    expect(await screen.findByText("Alice One")).toBeVisible();
    expect(await screen.findByText("No compensation records")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Add compensation record" }));
    fireEvent.change(screen.getByLabelText("Base amount"), { target: { value: "5000.00" } });
    fireEvent.change(screen.getByLabelText("Effective from"), { target: { value: "2026-03-01" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Add compensation record" })[1]);

    expect(await screen.findByText("SAR 5,000.00")).toBeVisible();
    expect(await screen.findByText("Standard Structure")).toBeVisible();
  });
});
