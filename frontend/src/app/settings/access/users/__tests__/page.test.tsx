import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";

import type { MeResponse } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/render";

import UsersPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-admin", email: "admin@example.com", status: "ACTIVE" },
  roles: ["ADMIN"],
  permissions: ["iam:user:read", "iam:user:write"],
  scope: {
    tenant_id: "t-1",
    company_id: null,
    branch_id: null,
    allowed_tenant_ids: ["t-1"],
    allowed_company_ids: [],
    allowed_branch_ids: [],
  },
};

describe("/settings/access/users", () => {
  it(
    "renders users list with meta",
    async () => {
    server.use(
      http.get("*/api/v1/iam/users", ({ request }) => {
        const url = new URL(request.url);
        const limit = Number(url.searchParams.get("limit") ?? "50");
        const offset = Number(url.searchParams.get("offset") ?? "0");
        return HttpResponse.json({
          ok: true,
          data: [
            {
              id: "u-1",
              email: "a@example.com",
              phone: null,
              status: "ACTIVE",
              created_at: "2026-02-01T10:00:00Z",
            },
            {
              id: "u-2",
              email: "b@example.com",
              phone: "+966555",
              status: "DISABLED",
              created_at: "2026-02-02T10:00:00Z",
            },
          ],
          meta: { limit, offset, total: 2 },
        });
      })
    );

    useAuth.getState().setFromSession(SESSION);
    renderWithProviders(<UsersPage />);

    expect(await screen.findByText("a@example.com")).toBeVisible();
    expect(screen.getByText("b@example.com")).toBeVisible();
    },
    // CI/Docker can be slower; allow extra time for initial render + query.
    15_000
  );
});
