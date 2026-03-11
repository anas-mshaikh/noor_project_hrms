import { describe, expect, it } from "vitest";
import { delay, http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { EmployeeDirectoryRowOut, HrEmployee360Out, MeResponse } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope, seedSession } from "@/test/utils/selection";
import { routerPush } from "@/test/utils/router";

import HrEmployeesPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-hr", email: "hr@example.com", status: "ACTIVE" },
  roles: ["HR_ADMIN"],
  permissions: ["hr:employee:read", "hr:employee:write", "tenancy:read"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

describe("/hr/employees", () => {
  it("renders loading state (skeleton rows)", async () => {
    server.use(
      http.get("*/api/v1/hr/employees", async () => {
        await delay(80);
        return HttpResponse.json(ok({ items: [], paging: { limit: 25, offset: 0, total: 0 } }));
      })
    );

    seedSession(SESSION);
    seedScope({
      tenantId: SESSION.scope.tenant_id,
      companyId: SESSION.scope.company_id,
      branchId: SESSION.scope.branch_id,
    });
    const { container } = renderWithProviders(<HrEmployeesPage />);

    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
    await screen.findByText("No employees");
  });

  it("renders empty state", async () => {
    server.use(
      http.get("*/api/v1/hr/employees", () =>
        HttpResponse.json(ok({ items: [], paging: { limit: 25, offset: 0, total: 0 } }))
      )
    );

    seedSession(SESSION);
    seedScope({
      tenantId: SESSION.scope.tenant_id,
      companyId: SESSION.scope.company_id,
      branchId: SESSION.scope.branch_id,
    });
    renderWithProviders(<HrEmployeesPage />);

    expect(await screen.findByText("No employees")).toBeVisible();
    expect(screen.getAllByRole("button", { name: /add employee/i })[0]).toBeEnabled();
  });

  it("renders employees from the directory", async () => {
    const rows: EmployeeDirectoryRowOut[] = [
      {
        employee_id: "e-1",
        employee_code: "E0001",
        status: "ACTIVE",
        full_name: "Alice One",
        email: "alice@example.com",
        phone: null,
        branch_id: "b-1",
        org_unit_id: null,
        manager_employee_id: null,
        manager_name: null,
        has_user_link: true,
      },
    ];

    server.use(
      http.get("*/api/v1/hr/employees", () =>
        HttpResponse.json(ok({ items: rows, paging: { limit: 25, offset: 0, total: rows.length } }))
      )
    );

    seedSession(SESSION);
    seedScope({
      tenantId: SESSION.scope.tenant_id,
      companyId: SESSION.scope.company_id,
      branchId: SESSION.scope.branch_id,
    });
    renderWithProviders(<HrEmployeesPage />);

    expect(await screen.findByText("E0001")).toBeVisible();
    expect(screen.getByText("Alice One")).toBeVisible();
    expect(screen.getByText("Enabled")).toBeVisible();
  });

  it(
    "creates an employee and routes to the profile",
    async () => {
      const rows: EmployeeDirectoryRowOut[] = [];

      server.use(
        http.get("*/api/v1/tenancy/branches", () =>
          HttpResponse.json(
            ok([
              {
                id: SESSION.scope.branch_id,
                tenant_id: SESSION.scope.tenant_id,
                company_id: SESSION.scope.company_id,
                name: "HQ",
                code: "HQ",
                timezone: null,
                address: {},
                status: "ACTIVE",
              },
            ])
          )
        ),
        http.get("*/api/v1/hr/employees", () =>
          HttpResponse.json(ok({ items: rows, paging: { limit: 25, offset: 0, total: rows.length } }))
        ),
        http.post("*/api/v1/hr/employees", async ({ request }) => {
          const body = (await request.json()) as {
            employee: {
              company_id: string;
              employee_code: string;
              status?: string | null;
              join_date?: string | null;
            };
            person: {
              first_name: string;
              last_name: string;
              email?: string | null;
              phone?: string | null;
            };
          };
          const employeeId = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee";
          const created: HrEmployee360Out = {
            employee: {
              id: employeeId,
              tenant_id: SESSION.scope.tenant_id,
              company_id: body.employee.company_id,
              person_id: "p-1",
              employee_code: body.employee.employee_code,
              status: body.employee.status ?? "ACTIVE",
              join_date: body.employee.join_date ?? null,
              termination_date: null,
              created_at: new Date(0).toISOString(),
              updated_at: new Date(0).toISOString(),
            },
            person: {
              id: "p-1",
              tenant_id: SESSION.scope.tenant_id,
              first_name: body.person.first_name,
              last_name: body.person.last_name,
              dob: null,
              nationality: null,
              email: body.person.email ?? null,
              phone: body.person.phone ?? null,
              address: {},
              created_at: new Date(0).toISOString(),
              updated_at: new Date(0).toISOString(),
            },
            current_employment: null,
            manager: null,
            linked_user: null,
          };

          rows.push({
            employee_id: created.employee.id,
            employee_code: created.employee.employee_code,
            status: created.employee.status,
            full_name: `${created.person.first_name} ${created.person.last_name}`.trim(),
            email: created.person.email,
            phone: created.person.phone,
            branch_id: SESSION.scope.branch_id,
            org_unit_id: null,
            manager_employee_id: null,
            manager_name: null,
            has_user_link: false,
          });

          return HttpResponse.json(ok(created));
        })
      );

      seedSession(SESSION);
      seedScope({
        tenantId: SESSION.scope.tenant_id,
        companyId: SESSION.scope.company_id,
        branchId: SESSION.scope.branch_id,
      });
      renderWithProviders(<HrEmployeesPage />);

      await screen.findByText("No employees");
      fireEvent.click(screen.getAllByRole("button", { name: /add employee/i })[0]);

      fireEvent.change(screen.getByLabelText("Employee code"), { target: { value: "E0001" } });
      fireEvent.change(screen.getByLabelText("First name"), { target: { value: "Alice" } });
      fireEvent.change(screen.getByLabelText("Last name"), { target: { value: "One" } });

      fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

      expect(await screen.findByText("E0001")).toBeVisible();
      expect(routerPush).toHaveBeenCalledWith("/hr/employees/eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee");
    },
    15_000
  );
});
