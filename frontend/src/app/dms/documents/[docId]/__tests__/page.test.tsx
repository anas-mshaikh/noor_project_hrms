import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";

import type { DmsDocumentOut, MeResponse } from "@/lib/types";
import { fail, ok } from "@/test/msw/builders/response";
import { routerReplace, setSearchParams } from "@/test/utils/router";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedSession } from "@/test/utils/selection";

import DmsDocumentCompatibilityPage from "../page";

const DOC_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const EMPLOYEE_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";

const SESSION: MeResponse = {
  user: { id: "u-emp", email: "employee@example.com", status: "ACTIVE" },
  roles: ["EMPLOYEE"],
  permissions: ["dms:document:read"],
  scope: {
    tenant_id: "tttttttt-tttt-4ttt-8ttt-tttttttttttt",
    company_id: null,
    branch_id: null,
    allowed_tenant_ids: ["tttttttt-tttt-4ttt-8ttt-tttttttttttt"],
    allowed_company_ids: [],
    allowed_branch_ids: [],
  },
};

function sampleDoc(): DmsDocumentOut {
  const now = new Date(0).toISOString();
  return {
    id: DOC_ID,
    tenant_id: SESSION.scope.tenant_id,
    document_type_id: "type-1",
    document_type_code: "ID",
    document_type_name: "National ID",
    owner_employee_id: "employee-1",
    status: "VERIFIED",
    expires_at: null,
    current_version_id: "version-1",
    current_version: {
      id: "version-1",
      tenant_id: SESSION.scope.tenant_id,
      document_id: DOC_ID,
      file_id: "file-1",
      version: 1,
      notes: null,
      created_by_user_id: SESSION.user.id,
      created_at: now,
    },
    verified_at: now,
    verified_by_user_id: SESSION.user.id,
    rejected_reason: null,
    created_by_user_id: SESSION.user.id,
    verification_workflow_request_id: null,
    created_at: now,
    updated_at: now,
    meta: null,
  };
}

describe("/dms/documents/[docId]", () => {
  it("redirects straight to employee docs when employeeId is present", async () => {
    seedSession(SESSION);
    setSearchParams({ employeeId: EMPLOYEE_ID });

    renderWithProviders(<DmsDocumentCompatibilityPage params={{ docId: DOC_ID }} />);

    expect(routerReplace).toHaveBeenCalledWith(`/dms/employee-docs?employeeId=${EMPLOYEE_ID}&docId=${DOC_ID}`);
  });

  it("resolves to My Documents when ESS can open the document directly", async () => {
    server.use(
      http.get(`*/api/v1/ess/me/documents/${DOC_ID}`, () => HttpResponse.json(ok(sampleDoc()))),
    );

    seedSession(SESSION);
    setSearchParams({});

    renderWithProviders(<DmsDocumentCompatibilityPage params={{ docId: DOC_ID }} />);

    await waitFor(() => {
      expect(routerReplace).toHaveBeenLastCalledWith(`/dms/my-docs?docId=${DOC_ID}`);
    });
  });

  it("shows a recovery screen when the document cannot be resolved", async () => {
    server.use(
      http.get(`*/api/v1/ess/me/documents/${DOC_ID}`, () =>
        HttpResponse.json(
          fail("dms.document.not_found", "Document not found", { correlation_id: "cid-dms-compat" }),
          { status: 404 },
        ),
      ),
    );

    seedSession(SESSION);
    setSearchParams({});

    renderWithProviders(<DmsDocumentCompatibilityPage params={{ docId: DOC_ID }} />);

    expect(await screen.findByText("Not found")).toBeVisible();
    expect(screen.getByText("The requested document does not exist or is not accessible.")).toBeVisible();
    expect(await screen.findByText(`Document ID: ${DOC_ID}`)).toBeVisible();
  });
});
