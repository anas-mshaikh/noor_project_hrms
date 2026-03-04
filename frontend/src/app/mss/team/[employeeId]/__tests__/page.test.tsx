import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";

import type { MeResponse, MssEmployeeProfileOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";
import { setParams } from "@/test/utils/router";

import MssTeamMemberPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-mgr", email: "manager@example.com", status: "ACTIVE" },
  roles: ["MANAGER"],
  permissions: ["hr:team:read"],
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

describe("/mss/team/[employeeId]", () => {
  it("loads member details and does not render sensitive fields", async () => {
    const profile: MssEmployeeProfileOut = {
      employee: {
        id: EMPLOYEE_ID,
        employee_code: "E0001",
        status: "ACTIVE",
        join_date: "2026-01-01",
        termination_date: null,
      },
      person: {
        first_name: "Alice",
        last_name: "One",
        email: "alice.one@example.com",
        phone: null,
      },
      current_employment: {
        branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
        org_unit_id: null,
        job_title_id: null,
        grade_id: null,
        manager_employee_id: null,
      },
      manager: null,
    };

    server.use(
      http.get("*/api/v1/mss/team/11111111-1111-4111-8111-111111111111", () =>
        HttpResponse.json(ok(profile))
      )
    );

    seedSession(SESSION);
    setParams({ employeeId: EMPLOYEE_ID });
    renderWithProviders(<MssTeamMemberPage params={{ employeeId: EMPLOYEE_ID }} />);

    expect(await screen.findByText("E0001")).toBeVisible();
    expect(await screen.findByText("Alice One")).toBeVisible();
    expect(await screen.findByText("alice.one@example.com")).toBeVisible();

    // Sensitive fields should not be present in MSS views.
    expect(screen.queryByText(/address/i)).toBeNull();
    expect(screen.queryByText(/nationality/i)).toBeNull();
    expect(screen.queryByText(/\bdob\b/i)).toBeNull();
  });
});

