import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/render";
import { useAuth } from "@/lib/auth";
import { useSelection } from "@/lib/selection";
import { routerPush } from "@/test/utils/router";

import SetupPage from "../page";

describe("/setup", () => {
  it("bootstraps successfully and routes to /scope", async () => {
    server.use(
      http.post("*/api/v1/bootstrap", () =>
        HttpResponse.json({
          ok: true,
          data: {
            user: { id: "u-1", email: "admin@example.com", status: "ACTIVE" },
            roles: ["ADMIN"],
            permissions: ["tenancy:write"],
            scope: {
              tenant_id: "t-1",
              company_id: "c-1",
              branch_id: "b-1",
              allowed_tenant_ids: ["t-1"],
              allowed_company_ids: ["c-1"],
              allowed_branch_ids: ["b-1"],
            },
          },
        })
      )
    );

    renderWithProviders(<SetupPage />);

    fireEvent.click(screen.getByRole("button", { name: /bootstrap/i }));

    await waitFor(() => {
      expect(routerPush).toHaveBeenCalledWith("/scope?reason=bootstrap");
    });

    expect(useAuth.getState().user?.email).toBe("admin@example.com");
    expect(useSelection.getState().tenantId).toBe("t-1");
    expect(useSelection.getState().companyId).toBe("c-1");
    expect(useSelection.getState().branchId).toBe("b-1");
  });

  it("shows an 'Already configured' state when bootstrap is rejected", async () => {
    server.use(
      http.post("*/api/v1/bootstrap", () =>
        HttpResponse.json(
          {
            ok: false,
            error: {
              code: "already_bootstrapped",
              message: "Bootstrap is only allowed on a fresh database",
              correlation_id: "cid-409",
            },
          },
          { status: 409 }
        )
      )
    );

    renderWithProviders(<SetupPage />);

    fireEvent.click(screen.getByRole("button", { name: /bootstrap/i }));

    expect(await screen.findByText(/^already configured$/i)).toBeVisible();
  });
});

