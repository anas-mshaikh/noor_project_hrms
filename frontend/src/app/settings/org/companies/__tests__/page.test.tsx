import { describe, expect, it } from "vitest";
import { http, HttpResponse, delay } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { MeResponse, CompanyOut } from "@/lib/types";
import { useAuth } from "@/lib/auth";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";

import CompaniesPage from "../page";

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

describe("/settings/org/companies", () => {
  it("renders loading state (skeleton rows)", async () => {
    server.use(
      http.get("*/api/v1/tenancy/companies", async () => {
        await delay(80);
        return HttpResponse.json(ok([]));
      })
    );

    useAuth.getState().setFromSession(SESSION);
    const { container } = renderWithProviders(<CompaniesPage />);

    expect(container.querySelectorAll('[data-slot="skeleton"]').length).toBeGreaterThan(0);
    await screen.findByText("No companies yet");
  });

  it("renders empty state", async () => {
    server.use(
      http.get("*/api/v1/tenancy/companies", () => HttpResponse.json(ok([])))
    );

    useAuth.getState().setFromSession(SESSION);
    renderWithProviders(<CompaniesPage />);

    expect(await screen.findByText("No companies yet")).toBeVisible();
    expect(screen.getAllByRole("button", { name: /create company/i })[0]).toBeEnabled();
  });

  it(
    "creates a company and shows it in the table",
    async () => {
    const companies: CompanyOut[] = [];

    server.use(
      http.get("*/api/v1/tenancy/companies", () => HttpResponse.json(ok(companies))),
      http.post("*/api/v1/tenancy/companies", async ({ request }) => {
        const body = (await request.json()) as {
          name: string;
          legal_name?: string | null;
          currency_code?: string | null;
          timezone?: string | null;
        };
        const created: CompanyOut = {
          id: `c-${companies.length + 1}`,
          tenant_id: "t-1",
          name: body.name,
          legal_name: body.legal_name ?? null,
          currency_code: body.currency_code ?? null,
          timezone: body.timezone ?? null,
          status: "ACTIVE",
        };
        companies.push(created);
        return HttpResponse.json(ok(created));
      })
    );

    useAuth.getState().setFromSession(SESSION);
    renderWithProviders(<CompaniesPage />);

    await screen.findByText("No companies yet");
    fireEvent.click(screen.getAllByRole("button", { name: /create company/i })[0]);

    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Noor LLC" } });
    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    expect(await screen.findByText("Noor LLC")).toBeVisible();
    },
    // CI/Docker can be slower; this flow includes a mutation + refetch + re-render.
    15_000
  );
});
