import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { HrEmployee360Out, MeResponse } from "@/lib/types";
import { fail, ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";

import EssMeProfilePage from "../page";

const SESSION: MeResponse = {
  user: { id: "u-ess", email: "employee@example.com", status: "ACTIVE" },
  roles: ["EMPLOYEE"],
  permissions: ["ess:profile:read", "ess:profile:write"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

describe("/ess/me", () => {
  it("loads profile and updates fields via PATCH", async () => {
    let profile: HrEmployee360Out = {
      employee: {
        id: "11111111-1111-4111-8111-111111111111",
        tenant_id: SESSION.scope.tenant_id,
        company_id: SESSION.scope.company_id!,
        person_id: "22222222-2222-4222-8222-222222222222",
        employee_code: "E0001",
        status: "ACTIVE",
        join_date: null,
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
      http.get("*/api/v1/ess/me/profile", () => HttpResponse.json(ok(profile))),
      http.patch("*/api/v1/ess/me/profile", async ({ request }) => {
        const body = (await request.json()) as { email?: string | null; phone?: string | null; address?: unknown };
        profile = {
          ...profile,
          person: {
            ...profile.person,
            email: body.email ?? null,
            phone: body.phone ?? null,
            address: (body.address as any) ?? {},
          },
        };
        return HttpResponse.json(ok(profile));
      })
    );

    seedSession(SESSION);
    renderWithProviders(<EssMeProfilePage />);

    expect(await screen.findByText("My Profile")).toBeVisible();
    expect(await screen.findByDisplayValue("alice.one@example.com")).toBeVisible();

    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "new@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /save changes/i }));

    expect(await screen.findByDisplayValue("new@example.com")).toBeVisible();
  });

  it("renders a guided state when the account is not linked", async () => {
    server.use(
      http.get("*/api/v1/ess/me/profile", () =>
        HttpResponse.json(
          fail("ess.not_linked", "User is not linked to an employee", {
            correlation_id: "cid-ess-not-linked",
          }),
          { status: 409 }
        )
      )
    );

    seedSession(SESSION);
    renderWithProviders(<EssMeProfilePage />);

    expect(await screen.findByText("Account not linked")).toBeVisible();
    expect(await screen.findByText("cid-ess-not-linked")).toBeVisible();
    expect(screen.getByRole("button", { name: /copy ref/i })).toBeVisible();
  });
});

