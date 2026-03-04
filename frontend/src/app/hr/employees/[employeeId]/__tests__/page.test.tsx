import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { HrEmployee360Out, MeResponse } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope, seedSession } from "@/test/utils/selection";
import { setParams } from "@/test/utils/router";

import HrEmployeeDetailPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-hr", email: "hr@example.com", status: "ACTIVE" },
  roles: ["HR_ADMIN"],
  permissions: ["hr:employee:read", "hr:employee:write", "tenancy:read", "iam:user:read"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

const EMPLOYEE_ID = "11111111-1111-4111-8111-111111111111";

describe("/hr/employees/[employeeId]", () => {
  it("fails closed for invalid employeeId params (no API call)", async () => {
    seedSession(SESSION);
    seedScope({
      tenantId: SESSION.scope.tenant_id,
      companyId: SESSION.scope.company_id,
      branchId: SESSION.scope.branch_id,
    });

    setParams({ employeeId: "undefined" });
    renderWithProviders(<HrEmployeeDetailPage params={{ employeeId: "undefined" }} />);

    expect(await screen.findByText("Invalid employee id")).toBeVisible();
    expect(screen.getByRole("link", { name: /back to employees/i })).toBeVisible();
  });

  it("loads and renders the employee overview for a valid UUID", async () => {
    const employee: HrEmployee360Out = {
      employee: {
        id: EMPLOYEE_ID,
        tenant_id: SESSION.scope.tenant_id,
        company_id: SESSION.scope.company_id!,
        person_id: "22222222-2222-4222-8222-222222222222",
        employee_code: "E0001",
        status: "ACTIVE",
        join_date: "2026-01-01",
        termination_date: null,
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
      },
      person: {
        id: "22222222-2222-4222-8222-222222222222",
        tenant_id: SESSION.scope.tenant_id,
        first_name: "Alice",
        last_name: "One",
        dob: null,
        nationality: null,
        email: "alice.one@example.com",
        phone: null,
        address: {},
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
      },
      current_employment: {
        id: "33333333-3333-4333-8333-333333333333",
        tenant_id: SESSION.scope.tenant_id,
        company_id: SESSION.scope.company_id!,
        employee_id: EMPLOYEE_ID,
        branch_id: SESSION.scope.branch_id!,
        org_unit_id: null,
        job_title_id: null,
        grade_id: null,
        manager_employee_id: null,
        start_date: "2026-01-01",
        end_date: null,
        is_primary: true,
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
      },
      manager: null,
      linked_user: null,
    };

    server.use(
      http.get("*/api/v1/hr/employees/11111111-1111-4111-8111-111111111111", () =>
        HttpResponse.json(ok(employee))
      )
    );

    seedSession(SESSION);
    seedScope({
      tenantId: SESSION.scope.tenant_id,
      companyId: SESSION.scope.company_id,
      branchId: SESSION.scope.branch_id,
    });

    setParams({ employeeId: EMPLOYEE_ID });
    renderWithProviders(<HrEmployeeDetailPage params={{ employeeId: EMPLOYEE_ID }} />);

    expect(await screen.findByRole("heading", { name: "E0001" })).toBeVisible();
    expect(await screen.findByText("Alice One")).toBeVisible();
    expect(await screen.findByText("Contact")).toBeVisible();
    expect(await screen.findByText("alice.one@example.com")).toBeVisible();
  });

  it("links a user and shows the linked user after refresh", async () => {
    const userId = "99999999-9999-4999-8999-999999999999";
    const linkedAt = new Date(0).toISOString();

    const employee: HrEmployee360Out = {
      employee: {
        id: EMPLOYEE_ID,
        tenant_id: SESSION.scope.tenant_id,
        company_id: SESSION.scope.company_id!,
        person_id: "22222222-2222-4222-8222-222222222222",
        employee_code: "E0001",
        status: "ACTIVE",
        join_date: "2026-01-01",
        termination_date: null,
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
      },
      person: {
        id: "22222222-2222-4222-8222-222222222222",
        tenant_id: SESSION.scope.tenant_id,
        first_name: "Alice",
        last_name: "One",
        dob: null,
        nationality: null,
        email: "alice.one@example.com",
        phone: null,
        address: {},
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
      },
      current_employment: null,
      manager: null,
      linked_user: null,
    };

    server.use(
      http.get("*/api/v1/hr/employees/11111111-1111-4111-8111-111111111111", () =>
        HttpResponse.json(ok(employee))
      ),
      http.get("*/api/v1/iam/users", ({ request }) => {
        const url = new URL(request.url);
        const q = url.searchParams.get("q") ?? "";
        if (!q) return HttpResponse.json(ok([], { limit: 10, offset: 0, total: 0 }));
        return HttpResponse.json(
          ok(
            [
              {
                id: userId,
                email: "user@example.com",
                phone: null,
                status: "ACTIVE",
                created_at: linkedAt,
              },
            ],
            { limit: 10, offset: 0, total: 1 }
          )
        );
      }),
      http.post("*/api/v1/hr/employees/11111111-1111-4111-8111-111111111111/link-user", async () => {
        // Simulate backend read model: after linking, GET employee includes linked_user.
        employee.linked_user = {
          user_id: userId,
          email: "user@example.com",
          status: "ACTIVE",
          linked_at: linkedAt,
        };
        return HttpResponse.json(
          ok({
            employee_id: EMPLOYEE_ID,
            user_id: userId,
            created_at: linkedAt,
          })
        );
      })
    );

    seedSession(SESSION);
    seedScope({
      tenantId: SESSION.scope.tenant_id,
      companyId: SESSION.scope.company_id,
      branchId: SESSION.scope.branch_id,
    });

    setParams({ employeeId: EMPLOYEE_ID });
    renderWithProviders(<HrEmployeeDetailPage params={{ employeeId: EMPLOYEE_ID }} />);

    // Wait for the employee to load before switching tabs.
    expect(await screen.findByRole("heading", { name: "E0001" })).toBeVisible();

    // Switch to the Link user tab.
    const linkUserTab = await screen.findByRole("tab", { name: /link user/i });
    // Radix Tabs switches on pointer/mouse down; `fireEvent.click` alone does not
    // dispatch the full event sequence.
    fireEvent.mouseDown(linkUserTab);
    fireEvent.click(linkUserTab);

    fireEvent.change(await screen.findByLabelText(/search users/i), { target: { value: "user@" } });
    fireEvent.click(await screen.findByRole("button", { name: /user@example.com/i }));
    fireEvent.click(screen.getByRole("button", { name: /^link user$/i }));

    expect(await screen.findByText(/linked user/i)).toBeVisible();
    expect(await screen.findByText("user@example.com (ACTIVE)")).toBeVisible();
  });
});
