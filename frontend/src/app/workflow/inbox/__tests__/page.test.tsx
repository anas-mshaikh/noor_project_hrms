import { describe, expect, it } from "vitest";
import { delay, http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { MeResponse, WorkflowRequestDetailOut, WorkflowRequestSummaryOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";
import { setPathname, setSearchParams } from "@/test/utils/router";

import WorkflowInboxPage from "../page";

const SESSION: MeResponse = {
  user: { id: "11111111-1111-4111-8111-111111111111", email: "approver@example.com", status: "ACTIVE" },
  roles: ["MANAGER"],
  permissions: ["workflow:request:read", "workflow:request:approve"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

describe("/workflow/inbox", () => {
  it("renders loading state (skeleton rows)", async () => {
    server.use(
      http.get("*/api/v1/workflow/inbox", async () => {
        await delay(80);
        return HttpResponse.json(ok({ items: [], next_cursor: null }));
      })
    );

    seedSession(SESSION);
    setPathname("/workflow/inbox");
    setSearchParams({});

    const { container } = renderWithProviders(<WorkflowInboxPage />);
    expect(container.querySelectorAll('[data-slot=\"skeleton\"]').length).toBeGreaterThan(0);
    expect(await screen.findByText("No requests")).toBeVisible();
  });

  it("selects a request and approves it (pending list updates)", async () => {
    const requestId = "22222222-2222-4222-8222-222222222222";

    let items: WorkflowRequestSummaryOut[] = [
      {
        id: requestId,
        request_type_code: "profile.change",
        status: "PENDING",
        current_step: 0,
        subject: "Employee profile change",
        payload: null,
        tenant_id: SESSION.scope.tenant_id,
        company_id: SESSION.scope.company_id!,
        branch_id: SESSION.scope.branch_id,
        created_by_user_id: null,
        requester_employee_id: "33333333-3333-4333-8333-333333333333",
        subject_employee_id: null,
        entity_type: null,
        entity_id: null,
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
      },
    ];

    const detail: WorkflowRequestDetailOut = {
      request: { ...items[0], payload: { field: "email", to: "new@example.com" } },
      steps: [],
      comments: [],
      attachments: [],
      events: [],
    };

    server.use(
      http.get("*/api/v1/workflow/inbox", () => HttpResponse.json(ok({ items, next_cursor: null }))),
      http.get("*/api/v1/workflow/requests/:id", ({ params }) => {
        expect(String(params.id)).toBe(requestId);
        return HttpResponse.json(ok(detail));
      }),
      http.post("*/api/v1/workflow/requests/:id/approve", ({ params }) => {
        expect(String(params.id)).toBe(requestId);
        items = [];
        return HttpResponse.json(ok({ id: requestId, status: "APPROVED", current_step: 0 }));
      })
    );

    seedSession(SESSION);
    setPathname("/workflow/inbox");
    setSearchParams({});

    renderWithProviders(<WorkflowInboxPage />);

    // List loads.
    expect(await screen.findByText("profile.change")).toBeVisible();

    // Select the row -> detail loads.
    // Click the row (text inside the button) to avoid brittle accessible-name matching.
    fireEvent.click(screen.getByText("profile.change"));
    expect(await screen.findByText("Employee profile change")).toBeVisible();
    expect(await screen.findByText("Payload")).toBeVisible();
    expect(await screen.findByText("email")).toBeVisible();

    // Approve -> list refetches to empty.
    fireEvent.click(screen.getByRole("button", { name: /^approve$/i }));
    expect(await screen.findByText("No requests")).toBeVisible();
  });
});
