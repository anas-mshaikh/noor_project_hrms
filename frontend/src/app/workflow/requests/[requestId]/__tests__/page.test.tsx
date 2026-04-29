import { describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { fireEvent, screen, waitFor } from "@testing-library/react";

import * as api from "@/lib/api";
import { createQueryClient } from "@/lib/queryClient";
import type { MeResponse, WorkflowRequestDetailOut } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";
import { setParams, setPathname, setSearchParams } from "@/test/utils/router";

import WorkflowRequestDeepLinkPage from "../page";

const SESSION: MeResponse = {
  user: { id: "11111111-1111-4111-8111-111111111111", email: "approver@example.com", status: "ACTIVE" },
  roles: ["MANAGER"],
  permissions: ["workflow:request:read", "workflow:request:approve", "dms:file:read", "dms:file:write"],
  scope: {
    tenant_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

describe("/workflow/requests/[requestId]", () => {
  it("renders request detail, posts comment, uploads attachment, and downloads it", async () => {
    const requestId = "22222222-2222-4222-8222-222222222222";
    const fileId = "00000000-0000-4000-8000-000000000001"; // from dms default handler

    let comments: Array<{ id: string; author_user_id: string; body: string; created_at: string }> = [];
    let attachments: Array<{ id: string; file_id: string; uploaded_by_user_id: string | null; note: string | null; created_at: string }> = [];

    function buildDetail(): WorkflowRequestDetailOut {
      return {
        request: {
          id: requestId,
          request_type_code: "profile.change",
          status: "PENDING",
          current_step: 0,
          subject: "Update email",
          payload: { field: "email", to: "new@example.com" },
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
        steps: [],
        comments,
        attachments,
        events: [],
      };
    }

    server.use(
      http.get("*/api/v1/workflow/requests/:id", ({ params }) => {
        expect(String(params.id)).toBe(requestId);
        return HttpResponse.json(ok(buildDetail()));
      }),
      http.post("*/api/v1/workflow/requests/:id/comments", async ({ params, request }) => {
        expect(String(params.id)).toBe(requestId);
        const body = (await request.json()) as { body: string };
        comments = [
          ...comments,
          {
            id: "c-1",
            author_user_id: SESSION.user.id,
            body: body.body,
            created_at: new Date(0).toISOString(),
          },
        ];
        return HttpResponse.json(ok({ id: "c-1", created_at: new Date(0).toISOString() }));
      }),
      http.post("*/api/v1/workflow/requests/:id/attachments", async ({ params, request }) => {
        expect(String(params.id)).toBe(requestId);
        const payload = (await request.json()) as { file_id: string; note?: string | null };
        expect(payload.file_id).toBe(fileId);
        attachments = [
          ...attachments,
          {
            id: "a-1",
            file_id: payload.file_id,
            uploaded_by_user_id: SESSION.user.id,
            note: payload.note ?? null,
            created_at: new Date(0).toISOString(),
          },
        ];
        return HttpResponse.json(ok({ id: "a-1", created_at: new Date(0).toISOString() }));
      }),
      http.get("*/api/v1/dms/files/:fileId/download", () => {
        return new HttpResponse(new Uint8Array([1, 2, 3]), {
          status: 200,
          headers: { "content-type": "application/octet-stream" },
        });
      })
    );

    const saveSpy = vi.spyOn(api, "saveBlobAsFile").mockImplementation(() => {});

    seedSession(SESSION);
    setPathname(`/workflow/requests/${requestId}`);
    setSearchParams({});
    setParams({ requestId });

    renderWithProviders(<WorkflowRequestDeepLinkPage params={{ requestId }} />);

    // Detail loads
    expect(await screen.findByText("profile.change")).toBeVisible();
    expect(screen.getByText("Update email")).toBeVisible();

    // Post comment
    fireEvent.change(screen.getByLabelText(/add comment/i), { target: { value: "LGTM" } });
    fireEvent.click(screen.getByRole("button", { name: /post comment/i }));
    expect(await screen.findByText("LGTM")).toBeVisible();

    // Upload attachment (dms upload is handled by default handler, returns fileId)
    const file = new File(["hello"], "hello.txt", { type: "text/plain" });
    fireEvent.change(screen.getByLabelText(/^file$/i), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText(/note/i), { target: { value: "evidence" } });
    fireEvent.click(screen.getByRole("button", { name: /upload & attach/i }));

    // Attachment appears with filename from DMS meta handler.
    expect(await screen.findByText("attachment.bin")).toBeVisible();

    // Download triggers saveBlobAsFile.
    fireEvent.click(screen.getByRole("button", { name: /download/i }));
    await waitFor(() => expect(saveSpy).toHaveBeenCalled());

    saveSpy.mockRestore();
  }, 60_000);

  it("renders DMS open-document affordances and invalidates DMS queries after approve", async () => {
    const requestId = "99999999-9999-4999-8999-999999999999";
    let status = "PENDING";
    const buildDetail = (): WorkflowRequestDetailOut => ({
      request: {
        id: requestId,
        request_type_code: "DOCUMENT_VERIFICATION",
        status,
        current_step: 0,
        subject: "Verify passport",
        payload: {
          document_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
          document_type_code: "PASSPORT",
          expires_at: "2026-12-31",
        },
        tenant_id: SESSION.scope.tenant_id,
        company_id: SESSION.scope.company_id!,
        branch_id: SESSION.scope.branch_id,
        created_by_user_id: SESSION.user.id,
        requester_employee_id: "33333333-3333-4333-8333-333333333333",
        subject_employee_id: "44444444-4444-4444-8444-444444444444",
        entity_type: "dms.document",
        entity_id: "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
      },
      steps: [],
      comments: [],
      attachments: [],
      events: [],
    });

    server.use(
      http.get("*/api/v1/workflow/requests/:id", () => HttpResponse.json(ok(buildDetail()))),
      http.post("*/api/v1/workflow/requests/:id/approve", () => {
        status = "APPROVED";
        return HttpResponse.json(ok({ id: requestId, status: "APPROVED", current_step: 0 }));
      }),
    );

    const queryClient = createQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    seedSession(SESSION);
    setPathname(`/workflow/requests/${requestId}`);
    setSearchParams({});
    setParams({ requestId });

    renderWithProviders(<WorkflowRequestDeepLinkPage params={{ requestId }} />, {
      queryClient,
    });

    const openLink = await screen.findByRole("link", { name: "Open document" });
    expect(openLink).toHaveAttribute(
      "href",
      "/dms/documents/aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa?employeeId=44444444-4444-4444-8444-444444444444",
    );
    expect(await screen.findByText("File name")).toBeVisible();
    expect(await screen.findByText("Available in document view")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ["dms"] }),
      ),
    );
  });

  it("renders payrun approval affordances and invalidates payroll queries after approve", async () => {
    const requestId = "aaaaaaaa-1111-4111-8111-aaaaaaaaaaaa";
    let status = "PENDING";
    const buildDetail = (): WorkflowRequestDetailOut => ({
      request: {
        id: requestId,
        request_type_code: "PAYRUN_APPROVAL",
        status,
        current_step: 0,
        subject: "Approve March payroll",
        payload: {
          payrun_id: "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb",
          period_key: "2026-03",
          branch_id: SESSION.scope.branch_id,
          totals: { net_total: "5000.00" },
        },
        tenant_id: SESSION.scope.tenant_id,
        company_id: SESSION.scope.company_id!,
        branch_id: SESSION.scope.branch_id,
        created_by_user_id: SESSION.user.id,
        requester_employee_id: "aaaaaaaa-3333-4333-8333-aaaaaaaaaaaa",
        subject_employee_id: null,
        entity_type: "payroll.payrun",
        entity_id: "bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb",
        created_at: new Date(0).toISOString(),
        updated_at: new Date(0).toISOString(),
      },
      steps: [],
      comments: [],
      attachments: [],
      events: [],
    });

    server.use(
      http.get("*/api/v1/workflow/requests/:id", () => HttpResponse.json(ok(buildDetail()))),
      http.post("*/api/v1/workflow/requests/:id/approve", () => {
        status = "APPROVED";
        return HttpResponse.json(ok({ id: requestId, status: "APPROVED", current_step: 0 }));
      }),
    );

    const queryClient = createQueryClient();
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    seedSession(SESSION);
    setPathname(`/workflow/requests/${requestId}`);
    setSearchParams({});
    setParams({ requestId });

    renderWithProviders(<WorkflowRequestDeepLinkPage params={{ requestId }} />, {
      queryClient,
    });

    const openLink = await screen.findByRole("link", { name: "Open payrun" });
    expect(openLink).toHaveAttribute(
      "href",
      "/payroll/payruns/bbbbbbbb-2222-4222-8222-bbbbbbbbbbbb",
    );
    expect(await screen.findByText("Payrun approval")).toBeVisible();
    expect(await screen.findByText("2026-03")).toBeVisible();

    fireEvent.click(screen.getByRole("button", { name: "Approve" }));

    await waitFor(() =>
      expect(invalidateSpy).toHaveBeenCalledWith(
        expect.objectContaining({ queryKey: ["payroll"] }),
      ),
    );
  });
});
