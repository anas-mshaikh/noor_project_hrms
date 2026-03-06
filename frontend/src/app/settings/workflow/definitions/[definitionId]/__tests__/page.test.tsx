import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { WorkflowDefinitionOut } from "@/lib/types";
import { fail, ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope } from "@/test/utils/selection";
import { setParams, setPathname, setSearchParams } from "@/test/utils/router";

import WorkflowDefinitionDetailPage from "../page";

describe("/settings/workflow/definitions/[definitionId]", () => {
  it("validates step requirements before saving", async () => {
    const definitionId = "11111111-1111-4111-8111-111111111111";
    const defs: WorkflowDefinitionOut[] = [
      {
        id: definitionId,
        tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        request_type_code: "leave.request",
        code: "LEAVE_DEFAULT",
        name: "Leave approvals",
        version: 1,
        is_active: false,
        created_by_user_id: null,
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
        steps: [
          {
            step_index: 0,
            assignee_type: "MANAGER",
            assignee_role_code: null,
            assignee_user_id: null,
            scope_mode: "TENANT",
            fallback_role_code: null,
          },
        ],
      },
    ];

    server.use(http.get("*/api/v1/workflow/definitions", () => HttpResponse.json(ok(defs))));

    seedScope({ tenantId: defs[0].tenant_id, companyId: defs[0].company_id, branchId: null });
    setPathname(`/settings/workflow/definitions/${definitionId}`);
    setSearchParams({});
    setParams({ definitionId });

    renderWithProviders(<WorkflowDefinitionDetailPage params={{ definitionId }} />);

    expect(await screen.findByText("Steps")).toBeVisible();

    // Switch assignee type to ROLE but do not provide role code.
    fireEvent.change(screen.getByLabelText(/assignee type/i), { target: { value: "ROLE" } });
    fireEvent.click(screen.getByRole("button", { name: /save steps/i }));

    expect(await screen.findByText(/ROLE requires role code/i)).toBeVisible();
  });

  it("shows correlation reference when activation fails", async () => {
    const definitionId = "22222222-2222-4222-8222-222222222222";
    const defs: WorkflowDefinitionOut[] = [
      {
        id: definitionId,
        tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
        request_type_code: "profile.change",
        code: "PROFILE_DEFAULT",
        name: "Profile approvals",
        version: 1,
        is_active: false,
        created_by_user_id: null,
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
        steps: [
          {
            step_index: 0,
            assignee_type: "MANAGER",
            assignee_role_code: null,
            assignee_user_id: null,
            scope_mode: "TENANT",
            fallback_role_code: null,
          },
        ],
      },
    ];

    server.use(
      http.get("*/api/v1/workflow/definitions", () => HttpResponse.json(ok(defs))),
      http.post("*/api/v1/workflow/definitions/:id/activate", ({ params }) => {
        expect(String(params.id)).toBe(definitionId);
        return HttpResponse.json(
          fail("workflow.definition.not_found", "Definition not found", {
            correlation_id: "cid-activate-1",
          }),
          { status: 404 }
        );
      })
    );

    seedScope({ tenantId: defs[0].tenant_id, companyId: defs[0].company_id, branchId: null });
    setPathname(`/settings/workflow/definitions/${definitionId}`);
    setSearchParams({});
    setParams({ definitionId });

    renderWithProviders(<WorkflowDefinitionDetailPage params={{ definitionId }} />);

    expect(await screen.findByText("Profile approvals")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: /^activate$/i }));

    expect(await screen.findByText(/reference/i)).toBeVisible();
    expect(screen.getByText(/cid-activate-1/i)).toBeVisible();
  });
});

