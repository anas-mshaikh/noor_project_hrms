import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";

import type { DmsDocumentOut, MeResponse } from "@/lib/types";
import { fail, ok } from "@/test/msw/builders/response";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";
import { setSearchParams } from "@/test/utils/router";

import MyDocumentsPage from "../page";

const DOC_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const SESSION: MeResponse = {
  user: { id: "u-emp", email: "employee@example.com", status: "ACTIVE" },
  roles: ["EMPLOYEE"],
  permissions: ["dms:document:read", "dms:file:read"],
  scope: {
    tenant_id: "tttttttt-tttt-4ttt-8ttt-tttttttttttt",
    company_id: "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
    branch_id: "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
    allowed_tenant_ids: ["tttttttt-tttt-4ttt-8ttt-tttttttttttt"],
    allowed_company_ids: ["bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb"],
    allowed_branch_ids: ["cccccccc-cccc-4ccc-8ccc-cccccccccccc"],
  },
};

function sampleDoc(): DmsDocumentOut {
  const now = new Date(0).toISOString();
  return {
    id: DOC_ID,
    tenant_id: SESSION.scope.tenant_id,
    document_type_id: "11111111-1111-4111-8111-111111111111",
    document_type_code: "ID",
    document_type_name: "National ID",
    owner_employee_id: "employee-1",
    status: "VERIFIED",
    expires_at: "2026-12-31",
    current_version_id: "22222222-2222-4222-8222-222222222222",
    current_version: {
      id: "22222222-2222-4222-8222-222222222222",
      tenant_id: SESSION.scope.tenant_id,
      document_id: DOC_ID,
      file_id: "33333333-3333-4333-8333-333333333333",
      version: 1,
      notes: null,
      created_by_user_id: SESSION.user.id,
      created_at: now,
    },
    verified_at: now,
    verified_by_user_id: "u-hr",
    rejected_reason: null,
    created_by_user_id: "u-hr",
    verification_workflow_request_id: null,
    created_at: now,
    updated_at: now,
    meta: null,
  };
}

describe("/dms/my-docs", () => {
  it("loads my documents and renders the selected detail", async () => {
    server.use(
      http.get("*/api/v1/ess/me/documents", () =>
        HttpResponse.json(ok({ items: [sampleDoc()], next_cursor: null })),
      ),
      http.get("*/api/v1/dms/files/:fileId", ({ params }) =>
        HttpResponse.json(
          ok({
            id: String(params.fileId),
            tenant_id: SESSION.scope.tenant_id,
            storage_provider: "LOCAL",
            original_filename: "national-id.pdf",
            content_type: "application/pdf",
            size_bytes: 2,
            sha256: null,
            status: "READY",
            created_by_user_id: SESSION.user.id,
            created_at: new Date(0).toISOString(),
            updated_at: new Date(0).toISOString(),
            meta: null,
          }),
        ),
      ),
    );

    seedSession(SESSION);
    setSearchParams({});

    renderWithProviders(<MyDocumentsPage />);

    expect(await screen.findByText("National ID")).toBeVisible();
    expect(await screen.findByText("Download current document")).toBeVisible();
  });

  it("shows neutral copy for a direct document id that is not accessible", async () => {
    server.use(
      http.get("*/api/v1/ess/me/documents", () =>
        HttpResponse.json(ok({ items: [], next_cursor: null })),
      ),
      http.get(`*/api/v1/ess/me/documents/${DOC_ID}`, () =>
        HttpResponse.json(
          fail("dms.document.not_found", "Document not found", { correlation_id: "cid-dms-my-doc" }),
          { status: 404 },
        ),
      ),
    );

    seedSession(SESSION);
    setSearchParams({ docId: DOC_ID });

    renderWithProviders(<MyDocumentsPage />);

    expect(await screen.findByText("Not found")).toBeVisible();
    expect(await screen.findByText("This document does not exist or is not accessible.")).toBeVisible();
  });
});
