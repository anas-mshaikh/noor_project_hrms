import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { WorkflowDefinitionOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope } from "@/test/utils/selection";

import WorkflowDefinitionsPage from "../page";

describe("/settings/workflow/definitions", () => {
  it("loads definitions list and supports creating a definition", async () => {
    let defs: WorkflowDefinitionOut[] = [
      {
        id: "11111111-1111-4111-8111-111111111111",
        tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        request_type_code: "leave.request",
        code: "LEAVE_DEFAULT",
        name: "Leave approvals",
        version: 1,
        is_active: true,
        created_by_user_id: null,
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
        steps: [],
      },
    ];

    server.use(
      http.get("*/api/v1/workflow/definitions", () => HttpResponse.json(ok(defs))),
      http.post("*/api/v1/workflow/definitions", async ({ request }) => {
        const payload = (await request.json()) as { request_type_code: string; code: string; name: string; version: number };
        const created: WorkflowDefinitionOut = {
          id: "22222222-2222-4222-8222-222222222222",
          tenant_id: defs[0].tenant_id,
          company_id: defs[0].company_id,
          request_type_code: payload.request_type_code,
          code: payload.code,
          name: payload.name,
          version: payload.version,
          is_active: false,
          created_by_user_id: null,
          created_at: new Date(0).toISOString(),
          updated_at: new Date(0).toISOString(),
          steps: [],
        };
        defs = [created, ...defs];
        return HttpResponse.json(ok(created));
      })
    );

    seedScope({
      tenantId: defs[0].tenant_id,
      companyId: defs[0].company_id,
      branchId: null,
    });

    renderWithProviders(<WorkflowDefinitionsPage />);

    // Existing row
    expect(await screen.findByText("Leave approvals")).toBeVisible();
    expect(screen.getByText("ACTIVE")).toBeVisible();

    // Create new definition
    fireEvent.click(screen.getByRole("button", { name: /create definition/i }));
    fireEvent.change(screen.getByLabelText(/request type code/i), { target: { value: "profile.change" } });
    fireEvent.change(screen.getByLabelText(/^code$/i), { target: { value: "PROFILE_DEFAULT" } });
    fireEvent.change(screen.getByLabelText(/^name$/i), { target: { value: "Profile approvals" } });
    fireEvent.change(screen.getByLabelText(/version/i), { target: { value: "1" } });
    fireEvent.click(screen.getByRole("button", { name: /^create$/i }));

    expect(await screen.findByText("Profile approvals")).toBeVisible();
  });
});

