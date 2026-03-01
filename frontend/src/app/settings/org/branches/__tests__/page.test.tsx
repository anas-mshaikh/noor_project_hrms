import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";

import type { MeResponse } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/render";

import BranchesPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-admin", email: "admin@example.com", status: "ACTIVE" },
  roles: ["ADMIN"],
  permissions: ["tenancy:read", "tenancy:write"],
  scope: {
    tenant_id: "t-1",
    company_id: null,
    branch_id: null,
    allowed_tenant_ids: ["t-1"],
    allowed_company_ids: [],
    allowed_branch_ids: [],
  },
};

describe("/settings/org/branches", () => {
  it("shows 'Create a company first' when no companies exist", async () => {
    server.use(
      http.get("*/api/v1/tenancy/companies", () => HttpResponse.json({ ok: true, data: [] })),
      http.get("*/api/v1/tenancy/branches", () => HttpResponse.json({ ok: true, data: [] }))
    );

    useAuth.getState().setFromSession(SESSION);
    renderWithProviders(<BranchesPage />);

    expect(await screen.findByText("Create a company first")).toBeVisible();
  });
});

