import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { IamRoleAssignIn, MeResponse, RoleOut, UserRoleOut } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/render";

import UserDetailPage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-admin", email: "admin@example.com", status: "ACTIVE" },
  roles: ["ADMIN"],
  // No tenancy:read => assignment UI falls back to UUID inputs (expected for this test).
  permissions: ["iam:user:read", "iam:role:assign"],
  scope: {
    tenant_id: "t-1",
    company_id: null,
    branch_id: null,
    allowed_tenant_ids: ["t-1"],
    allowed_company_ids: [],
    allowed_branch_ids: [],
  },
};

describe("/settings/access/users/[userId]", () => {
  it("validates branch role assignments and supports add/remove", async () => {
    const roles: RoleOut[] = [
      { code: "ADMIN", name: "Admin", description: "Full access" },
      { code: "HR_ADMIN", name: "HR Admin", description: null },
    ];

    const assignments: UserRoleOut[] = [];

    server.use(
      http.get("*/api/v1/iam/users/u-1", () =>
        HttpResponse.json({
          ok: true,
          data: {
            id: "u-1",
            email: "user1@example.com",
            phone: null,
            status: "ACTIVE",
            created_at: "2026-02-01T10:00:00Z",
          },
        })
      ),
      http.get("*/api/v1/iam/users/u-1/roles", () =>
        HttpResponse.json({ ok: true, data: assignments })
      ),
      http.get("*/api/v1/iam/roles", () => HttpResponse.json({ ok: true, data: roles })),
      http.post("*/api/v1/iam/users/u-1/roles", async ({ request }) => {
        const body = (await request.json()) as IamRoleAssignIn;
        const created: UserRoleOut = {
          role_code: body.role_code,
          tenant_id: "t-1",
          company_id: body.company_id ?? null,
          branch_id: body.branch_id ?? null,
          created_at: "2026-02-03T10:00:00Z",
        };
        assignments.unshift(created);
        return HttpResponse.json({ ok: true, data: created });
      }),
      http.delete("*/api/v1/iam/users/u-1/roles", ({ request }) => {
        const url = new URL(request.url);
        const roleCode = url.searchParams.get("role_code");
        const companyId = url.searchParams.get("company_id");
        const branchId = url.searchParams.get("branch_id");

        const idx = assignments.findIndex(
          (r) =>
            r.role_code === roleCode &&
            String(r.company_id ?? "") === String(companyId ?? "") &&
            String(r.branch_id ?? "") === String(branchId ?? "")
        );
        if (idx >= 0) assignments.splice(idx, 1);
        return HttpResponse.json({ ok: true, data: { deleted: true } });
      })
    );

    useAuth.getState().setFromSession(SESSION);
    renderWithProviders(<UserDetailPage params={{ userId: "u-1" }} />);

    expect(
      await screen.findByRole("heading", { name: "user1@example.com" })
    ).toBeVisible();

    // Go to Role assignments tab.
    const rolesTab = screen.getByRole("tab", { name: /role assignments/i });
    // Radix Tabs switches on pointer/mouse down; `fireEvent.click` alone does not
    // dispatch the full event sequence.
    fireEvent.mouseDown(rolesTab);
    fireEvent.click(rolesTab);
    // The page shows an "Add role" CTA in both the toolbar and the empty state.
    // Click the first (toolbar) one to open the assignment sheet.
    const addRoleButtons = await screen.findAllByRole("button", { name: /add role/i });
    fireEvent.click(addRoleButtons[0]!);

    // Select role and scope=Branch, but leave company/branch ids empty.
    fireEvent.change(screen.getByLabelText("Role"), { target: { value: "ADMIN" } });
    fireEvent.change(screen.getByLabelText("Scope"), { target: { value: "BRANCH" } });
    fireEvent.click(screen.getByRole("button", { name: /^assign$/i }));
    expect(await screen.findByText("Company is required.")).toBeVisible();

    fireEvent.change(screen.getByLabelText("Company ID"), { target: { value: "c-1" } });
    fireEvent.click(screen.getByRole("button", { name: /^assign$/i }));
    expect(await screen.findByText("Branch is required.")).toBeVisible();

    fireEvent.change(screen.getByLabelText("Branch ID"), { target: { value: "b-1" } });
    fireEvent.click(screen.getByRole("button", { name: /^assign$/i }));

    expect(await screen.findByText("ADMIN")).toBeVisible();

    // Remove the role assignment.
    fireEvent.click(screen.getByRole("button", { name: /remove/i }));
    fireEvent.click(screen.getByRole("button", { name: /^remove$/i }));

    expect(await screen.findByText("No role assignments")).toBeVisible();
  });
});

