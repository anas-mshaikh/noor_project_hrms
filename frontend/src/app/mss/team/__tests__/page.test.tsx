import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { MeResponse, MssTeamListOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope, seedSession } from "@/test/utils/selection";

import MssTeamPage from "../page";

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

describe("/mss/team", () => {
  it("loads the team list and supports depth switching", async () => {
    const seenDepths: string[] = [];

    server.use(
      http.get("*/api/v1/mss/team", ({ request }) => {
        const url = new URL(request.url);
        seenDepths.push(url.searchParams.get("depth") ?? "");

        const out: MssTeamListOut = {
          items: [
            {
              employee_id: "11111111-1111-4111-8111-111111111111",
              employee_code: "E0001",
              display_name: "Alice One",
              status: "ACTIVE",
              branch_id: null,
              org_unit_id: null,
              job_title_id: null,
              grade_id: null,
              manager_employee_id: null,
              relationship_depth: url.searchParams.get("depth") === "all" ? 2 : 1,
            },
          ],
          paging: { limit: 25, offset: 0, total: 1 },
        };
        return HttpResponse.json(ok(out));
      })
    );

    seedSession(SESSION);
    seedScope({
      tenantId: SESSION.scope.tenant_id,
      companyId: SESSION.scope.company_id,
      branchId: SESSION.scope.branch_id,
    });
    renderWithProviders(<MssTeamPage />);

    expect(await screen.findByText("E0001")).toBeVisible();
    expect(screen.getByText("Alice One")).toBeVisible();

    // Switch to all-depth view.
    fireEvent.change(screen.getByLabelText("Depth"), { target: { value: "all" } });
    expect(await screen.findByText("2")).toBeVisible();

    expect(seenDepths).toContain("1");
    expect(seenDepths).toContain("all");
  });
});

