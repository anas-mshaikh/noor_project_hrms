import { describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";

import * as api from "@/lib/api";
import type { MeResponse, PayrunDetailOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { setParams, setPathname } from "@/test/utils/router";
import { seedSession } from "@/test/utils/selection";

import PayrollPayrunDetailPage from "../page";

const TENANT_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const COMPANY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const BRANCH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const PAYRUN_ID = "77777777-7777-4777-8777-777777777777";
const PAYRUN_ITEM_ID = "88888888-8888-4888-8888-888888888888";
const WORKFLOW_REQUEST_ID = "99999999-9999-4999-8999-999999999999";
const SESSION: MeResponse = {
  user: { id: "u-payroll", email: "payroll@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: [
    "payroll:payrun:read",
    "payroll:payrun:submit",
    "payroll:payrun:publish",
    "payroll:payrun:export",
    "workflow:request:read",
  ],
  scope: {
    tenant_id: TENANT_ID,
    company_id: COMPANY_ID,
    branch_id: BRANCH_ID,
    allowed_tenant_ids: [TENANT_ID],
    allowed_company_ids: [COMPANY_ID],
    allowed_branch_ids: [BRANCH_ID],
  },
};

function buildDetail(status: string): PayrunDetailOut {
  const now = new Date(0).toISOString();
  return {
    payrun: {
      id: PAYRUN_ID,
      tenant_id: TENANT_ID,
      calendar_id: "11111111-1111-4111-8111-111111111111",
      period_id: "22222222-2222-4222-8222-222222222222",
      branch_id: BRANCH_ID,
      version: 1,
      status,
      generated_at: now,
      generated_by_user_id: null,
      workflow_request_id:
        status === "PENDING_APPROVAL" || status === "APPROVED" || status === "PUBLISHED"
          ? WORKFLOW_REQUEST_ID
          : null,
      idempotency_key: "payrun:test",
      totals_json: {
        included_count: 1,
        excluded_count: 1,
        gross_total: "5000.00",
        deductions_total: "0.00",
        net_total: "5000.00",
        currency_code: "SAR",
        computed_at: now,
      },
      created_at: now,
      updated_at: now,
    },
    items: [
      {
        id: PAYRUN_ITEM_ID,
        tenant_id: TENANT_ID,
        payrun_id: PAYRUN_ID,
        employee_id: "employee-1",
        payable_days: 31,
        payable_minutes: 14880,
        working_days_in_period: 31,
        gross_amount: "5000.00",
        deductions_amount: "0.00",
        net_amount: "5000.00",
        status: "INCLUDED",
        computed_json: { base_amount: "5000.00" },
        anomalies_json: null,
        created_at: now,
      },
      {
        id: "aaaaaaaa-bbbb-4ccc-8ddd-eeeeeeeeeeee",
        tenant_id: TENANT_ID,
        payrun_id: PAYRUN_ID,
        employee_id: "employee-2",
        payable_days: 0,
        payable_minutes: 0,
        working_days_in_period: 31,
        gross_amount: "0.00",
        deductions_amount: "0.00",
        net_amount: "0.00",
        status: "EXCLUDED",
        computed_json: {},
        anomalies_json: { NO_COMPENSATION: true },
        created_at: now,
      },
    ],
    lines: [
      {
        id: "line-1",
        tenant_id: TENANT_ID,
        payrun_item_id: PAYRUN_ITEM_ID,
        component_id: "component-1",
        component_code: "BASIC",
        component_type: "EARNING",
        amount: "5000.00",
        meta_json: null,
        created_at: now,
      },
    ],
  };
}

describe("/payroll/payruns/[payrunId]", () => {
  it("fails closed for invalid payrun ids", async () => {
    seedSession(SESSION);
    setPathname("/payroll/payruns/not-a-uuid");
    setParams({ payrunId: "not-a-uuid" });

    renderWithProviders(<PayrollPayrunDetailPage params={{ payrunId: "not-a-uuid" }} />);

    expect(await screen.findByText("Invalid payrun id")).toBeVisible();
  });

  it("renders employees and exceptions, exports, and submits approval", async () => {
    let status = "DRAFT";

    server.use(
      http.get(`*/api/v1/payroll/payruns/${PAYRUN_ID}`, () =>
        HttpResponse.json(ok(buildDetail(status))),
      ),
      http.post(`*/api/v1/payroll/payruns/${PAYRUN_ID}/submit-approval`, () => {
        status = "PENDING_APPROVAL";
        return HttpResponse.json(
          ok({ payrun_id: PAYRUN_ID, workflow_request_id: WORKFLOW_REQUEST_ID, status }),
        );
      }),
      http.get(`*/api/v1/payroll/payruns/${PAYRUN_ID}/export`, () =>
        new HttpResponse("employee_id,net_amount\nemployee-1,5000.00\n", {
          status: 200,
          headers: {
            "Content-Type": "text/csv",
            "Content-Disposition": 'attachment; filename="payrun.csv"',
          },
        }),
      ),
      http.get(`*/api/v1/workflow/requests/${WORKFLOW_REQUEST_ID}`, () =>
        HttpResponse.json(
          ok({
            request: {
              id: WORKFLOW_REQUEST_ID,
              request_type_code: "PAYRUN_APPROVAL",
              status,
              current_step: 0,
              subject: "Approve March payroll",
              payload: { period_key: "2026-03" },
              tenant_id: TENANT_ID,
              company_id: COMPANY_ID,
              branch_id: BRANCH_ID,
              created_by_user_id: SESSION.user.id,
              requester_employee_id: null,
              subject_employee_id: null,
              entity_type: "payroll.payrun",
              entity_id: PAYRUN_ID,
              created_at: new Date(0).toISOString(),
              updated_at: new Date(0).toISOString(),
            },
            steps: [],
            comments: [],
            attachments: [],
            events: [],
          }),
        ),
      ),
    );

    const saveSpy = vi.spyOn(api, "saveBlobAsFile").mockImplementation(() => {});

    seedSession(SESSION);
    setPathname(`/payroll/payruns/${PAYRUN_ID}`);
    setParams({ payrunId: PAYRUN_ID });

    renderWithProviders(<PayrollPayrunDetailPage params={{ payrunId: PAYRUN_ID }} />);

    expect(await screen.findByText("employee-1")).toBeVisible();
    expect(screen.getByRole("button", { name: "Publish" })).toBeDisabled();

    fireEvent.click(screen.getByRole("tab", { name: "Exceptions" }));
    expect(await screen.findByText("No compensation record")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Export CSV" }));
    await waitFor(() => expect(saveSpy).toHaveBeenCalled());

    fireEvent.click(screen.getByRole("button", { name: "Submit for approval" }));
    expect(await screen.findByRole("link", { name: "Open approval request" })).toHaveAttribute(
      "href",
      `/workflow/requests/${WORKFLOW_REQUEST_ID}`,
    );
    expect(screen.getByRole("button", { name: "Publish" })).toBeDisabled();

    saveSpy.mockRestore();
  });

  it("publishes an approved payrun", async () => {
    let status = "APPROVED";

    server.use(
      http.get(`*/api/v1/payroll/payruns/${PAYRUN_ID}`, () =>
        HttpResponse.json(ok(buildDetail(status))),
      ),
      http.post(`*/api/v1/payroll/payruns/${PAYRUN_ID}/publish`, () => {
        status = "PUBLISHED";
        return HttpResponse.json(ok({ payrun_id: PAYRUN_ID, published_count: 1, status }));
      }),
      http.get(`*/api/v1/workflow/requests/${WORKFLOW_REQUEST_ID}`, () =>
        HttpResponse.json(
          ok({
            request: {
              id: WORKFLOW_REQUEST_ID,
              request_type_code: "PAYRUN_APPROVAL",
              status: "APPROVED",
              current_step: 0,
              subject: "Approve March payroll",
              payload: { period_key: "2026-03" },
              tenant_id: TENANT_ID,
              company_id: COMPANY_ID,
              branch_id: BRANCH_ID,
              created_by_user_id: SESSION.user.id,
              requester_employee_id: null,
              subject_employee_id: null,
              entity_type: "payroll.payrun",
              entity_id: PAYRUN_ID,
              created_at: new Date(0).toISOString(),
              updated_at: new Date(0).toISOString(),
            },
            steps: [],
            comments: [],
            attachments: [],
            events: [],
          }),
        ),
      ),
    );

    seedSession(SESSION);
    setPathname(`/payroll/payruns/${PAYRUN_ID}`);
    setParams({ payrunId: PAYRUN_ID });

    renderWithProviders(<PayrollPayrunDetailPage params={{ payrunId: PAYRUN_ID }} />);

    const publishButton = await screen.findByRole("button", { name: "Publish" });
    expect(publishButton).toBeEnabled();

    fireEvent.click(publishButton);

    expect(await screen.findByText("Status Published")).toBeVisible();
  });
});
