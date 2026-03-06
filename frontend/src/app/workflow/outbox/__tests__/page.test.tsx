import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen } from "@testing-library/react";

import type { MeResponse, WorkflowRequestSummaryOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";
import { setPathname, setSearchParams } from "@/test/utils/router";

import WorkflowOutboxPage from "../page";

const SESSION: MeResponse = {
  user: { id: "11111111-1111-4111-8111-111111111111", email: "requester@example.com", status: "ACTIVE" },
  roles: ["EMPLOYEE"],
  permissions: ["workflow:request:read"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

describe("/workflow/outbox", () => {
  it("renders requests created by the user", async () => {
    const items: WorkflowRequestSummaryOut[] = [
      {
        id: "22222222-2222-4222-8222-222222222222",
        request_type_code: "leave.request",
        status: "PENDING",
        current_step: 0,
        subject: "Annual leave",
        payload: null,
        tenant_id: SESSION.scope.tenant_id,
        company_id: SESSION.scope.company_id!,
        branch_id: SESSION.scope.branch_id,
        created_by_user_id: SESSION.user.id,
        requester_employee_id: "33333333-3333-4333-8333-333333333333",
        subject_employee_id: null,
        entity_type: null,
        entity_id: null,
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
      },
    ];

    server.use(
      http.get("*/api/v1/workflow/outbox", () => HttpResponse.json(ok({ items, next_cursor: null })))
    );

    seedSession(SESSION);
    setPathname("/workflow/outbox");
    setSearchParams({});

    renderWithProviders(<WorkflowOutboxPage />);

    expect(await screen.findByText("leave.request")).toBeVisible();
    expect(screen.getByText("Annual leave")).toBeVisible();
    expect(screen.getByRole("button", { name: /cancel/i })).toBeEnabled();
  });

  it("cancels a pending request and updates the list", async () => {
    const requestId = "44444444-4444-4444-8444-444444444444";

    let items: WorkflowRequestSummaryOut[] = [
      {
        id: requestId,
        request_type_code: "profile.change",
        status: "PENDING",
        current_step: 0,
        subject: "Update phone",
        payload: null,
        tenant_id: SESSION.scope.tenant_id,
        company_id: SESSION.scope.company_id!,
        branch_id: SESSION.scope.branch_id,
        created_by_user_id: SESSION.user.id,
        requester_employee_id: "55555555-5555-4555-8555-555555555555",
        subject_employee_id: null,
        entity_type: null,
        entity_id: null,
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
      },
    ];

    server.use(
      http.get("*/api/v1/workflow/outbox", () => HttpResponse.json(ok({ items, next_cursor: null }))),
      http.post("*/api/v1/workflow/requests/:id/cancel", ({ params }) => {
        expect(String(params.id)).toBe(requestId);
        items = [];
        return HttpResponse.json(ok({ id: requestId, status: "CANCELED", cancelled_at: new Date(0).toISOString() }));
      })
    );

    seedSession(SESSION);
    setPathname("/workflow/outbox");
    setSearchParams({});

    renderWithProviders(<WorkflowOutboxPage />);

    expect(await screen.findByText("Update phone")).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /^cancel$/i }));

    expect(await screen.findByText(/cancel request/i)).toBeVisible();
    fireEvent.click(screen.getByRole("button", { name: /confirm cancel/i }));

    expect(await screen.findByText("No requests")).toBeVisible();
  });
});

