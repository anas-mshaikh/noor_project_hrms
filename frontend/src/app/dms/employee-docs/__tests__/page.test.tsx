import { describe, expect, it } from "vitest";
import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { DmsDocumentOut, EmployeeDirectoryRowOut, HrEmployee360Out, MeResponse } from "@/lib/types";
import { ok } from "@/test/msw/builders/response";
import { routerPush } from "@/test/utils/router";
import { server } from "@/test/msw/server";
import { renderWithProviders } from "@/test/utils/render";
import { seedScope, seedSession } from "@/test/utils/selection";
import { setSearchParams } from "@/test/utils/router";

import EmployeeDocsPage from "../page";

const EMPLOYEE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa";
const COMPANY_ID = "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb";
const BRANCH_ID = "cccccccc-cccc-4ccc-8ccc-cccccccccccc";
const DOC_ID = "dddddddd-dddd-4ddd-8ddd-dddddddddddd";

const SESSION: MeResponse = {
  user: { id: "u-hr", email: "hr@example.com", status: "ACTIVE" },
  roles: ["HR"],
  permissions: [
    "dms:document:read",
    "dms:document:write",
    "dms:document:verify",
    "dms:file:read",
    "dms:file:write",
    "hr:employee:read",
  ],
  scope: {
    tenant_id: "tttttttt-tttt-4ttt-8ttt-tttttttttttt",
    company_id: COMPANY_ID,
    branch_id: BRANCH_ID,
    allowed_tenant_ids: ["tttttttt-tttt-4ttt-8ttt-tttttttttttt"],
    allowed_company_ids: [COMPANY_ID],
    allowed_branch_ids: [BRANCH_ID],
  },
};

function employeeRow(): EmployeeDirectoryRowOut {
  return {
    employee_id: EMPLOYEE_ID,
    employee_code: "E0001",
    status: "ACTIVE",
    full_name: "Alice One",
    email: "alice@example.com",
    phone: null,
    branch_id: BRANCH_ID,
    org_unit_id: null,
    manager_employee_id: null,
    manager_name: null,
  };
}

function employee360(): HrEmployee360Out {
  const now = new Date(0).toISOString();
  return {
    employee: {
      id: EMPLOYEE_ID,
      tenant_id: SESSION.scope.tenant_id,
      company_id: COMPANY_ID,
      person_id: "11111111-1111-4111-8111-111111111111",
      employee_code: "E0001",
      status: "ACTIVE",
      join_date: "2026-01-01",
      termination_date: null,
      created_at: now,
      updated_at: now,
    },
    person: {
      id: "11111111-1111-4111-8111-111111111111",
      tenant_id: SESSION.scope.tenant_id,
      first_name: "Alice",
      last_name: "One",
      dob: null,
      nationality: null,
      email: "alice@example.com",
      phone: null,
      address: {},
      created_at: now,
      updated_at: now,
    },
    current_employment: {
      id: "22222222-2222-4222-8222-222222222222",
      tenant_id: SESSION.scope.tenant_id,
      company_id: COMPANY_ID,
      employee_id: EMPLOYEE_ID,
      branch_id: BRANCH_ID,
      org_unit_id: null,
      job_title_id: null,
      grade_id: null,
      manager_employee_id: null,
      start_date: "2026-01-01",
      end_date: null,
      is_primary: true,
      created_at: now,
      updated_at: now,
    },
    manager: null,
    linked_user: null,
  };
}

function sampleDoc(version = 1): DmsDocumentOut {
  const now = new Date(0).toISOString();
  return {
    id: DOC_ID,
    tenant_id: SESSION.scope.tenant_id,
    document_type_id: "33333333-3333-4333-8333-333333333333",
    document_type_code: "PASSPORT",
    document_type_name: "Passport",
    owner_employee_id: EMPLOYEE_ID,
    status: "SUBMITTED",
    expires_at: "2026-12-31",
    current_version_id: "44444444-4444-4444-8444-444444444444",
    current_version: {
      id: "44444444-4444-4444-8444-444444444444",
      tenant_id: SESSION.scope.tenant_id,
      document_id: DOC_ID,
      file_id: `55555555-5555-4555-8555-55555555555${version}`,
      version,
      notes: version > 1 ? "Updated file" : null,
      created_by_user_id: SESSION.user.id,
      created_at: now,
    },
    verified_at: null,
    verified_by_user_id: null,
    rejected_reason: null,
    created_by_user_id: SESSION.user.id,
    verification_workflow_request_id: null,
    created_at: now,
    updated_at: now,
    meta: null,
  };
}

describe("/dms/employee-docs", () => {
  it("fails closed when no employee is selected", async () => {
    seedSession(SESSION);
    seedScope({ tenantId: SESSION.scope.tenant_id, companyId: COMPANY_ID, branchId: BRANCH_ID });
    setSearchParams({});

    server.use(
      http.get("*/api/v1/hr/employees", () =>
        HttpResponse.json(ok({ items: [employeeRow()], paging: { limit: 8, offset: 0, total: 1 } })),
      ),
    );

    renderWithProviders(<EmployeeDocsPage />);

    expect(await screen.findByText("Select an employee to view documents.")).toBeVisible();
    expect(await screen.findByText("Alice One")).toBeVisible();
  });

  it("uploads a document for the selected employee", async () => {
    const user = userEvent.setup();
    const docs: DmsDocumentOut[] = [];
    let uploadCounter = 0;

    server.use(
      http.get("*/api/v1/hr/employees", () =>
        HttpResponse.json(ok({ items: [employeeRow()], paging: { limit: 8, offset: 0, total: 1 } })),
      ),
      http.get(`*/api/v1/hr/employees/${EMPLOYEE_ID}`, () => HttpResponse.json(ok(employee360()))),
      http.get("*/api/v1/dms/document-types", () =>
        HttpResponse.json(
          ok({
            items: [
              {
                id: "33333333-3333-4333-8333-333333333333",
                tenant_id: SESSION.scope.tenant_id,
                code: "PASSPORT",
                name: "Passport",
                requires_expiry: true,
                is_active: true,
                created_at: new Date(0).toISOString(),
                updated_at: new Date(0).toISOString(),
              },
            ],
          }),
        ),
      ),
      http.get(`*/api/v1/hr/employees/${EMPLOYEE_ID}/documents`, () =>
        HttpResponse.json(ok({ items: docs, next_cursor: null })),
      ),
      http.post("*/api/v1/dms/files", () => {
        uploadCounter += 1;
        return HttpResponse.json(
          ok({
            id: `66666666-6666-4666-8666-66666666666${uploadCounter}`,
            tenant_id: SESSION.scope.tenant_id,
            storage_provider: "LOCAL",
            original_filename: "passport.pdf",
            content_type: "application/pdf",
            size_bytes: 2,
            sha256: null,
            status: "READY",
            created_by_user_id: SESSION.user.id,
            created_at: new Date(0).toISOString(),
            updated_at: new Date(0).toISOString(),
            meta: null,
          }),
        );
      }),
      http.post(`*/api/v1/hr/employees/${EMPLOYEE_ID}/documents`, async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const created = {
          ...sampleDoc(),
          document_type_code: String(body.document_type_code),
          expires_at: String(body.expires_at),
        };
        docs.unshift(created);
        return HttpResponse.json(ok(created));
      }),
    );

    seedSession(SESSION);
    seedScope({ tenantId: SESSION.scope.tenant_id, companyId: COMPANY_ID, branchId: BRANCH_ID });
    setSearchParams({ employeeId: EMPLOYEE_ID });

    renderWithProviders(<EmployeeDocsPage />);

    await user.click(await screen.findByRole("button", { name: "Upload doc" }));
    await user.selectOptions(screen.getByLabelText("Document type"), "PASSPORT");
    await user.type(screen.getByLabelText("Expiry date (optional)"), "2026-12-31");
    await user.upload(
      screen.getByLabelText("File"),
      new File(["x"], "passport.pdf", { type: "application/pdf" })
    );
    await user.click(screen.getByRole("button", { name: /^Upload$/ }));

    expect((await screen.findAllByText("Passport")).length).toBeGreaterThan(0);
    expect((await screen.findAllByText("SUBMITTED")).length).toBeGreaterThan(0);
  }, 60_000);

  it("replaces the current document and requests verification", async () => {
    const user = userEvent.setup();
    const docs: DmsDocumentOut[] = [sampleDoc(1)];

    server.use(
      http.get("*/api/v1/hr/employees", () =>
        HttpResponse.json(ok({ items: [employeeRow()], paging: { limit: 8, offset: 0, total: 1 } })),
      ),
      http.get(`*/api/v1/hr/employees/${EMPLOYEE_ID}`, () => HttpResponse.json(ok(employee360()))),
      http.get("*/api/v1/dms/document-types", () => HttpResponse.json(ok({ items: [] }))),
      http.get(`*/api/v1/hr/employees/${EMPLOYEE_ID}/documents`, () =>
        HttpResponse.json(ok({ items: docs, next_cursor: null })),
      ),
      http.get("*/api/v1/dms/files/:fileId", ({ params }) =>
        HttpResponse.json(
          ok({
            id: String(params.fileId),
            tenant_id: SESSION.scope.tenant_id,
            storage_provider: "LOCAL",
            original_filename: "passport.pdf",
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
      http.post("*/api/v1/dms/files", () =>
        HttpResponse.json(
          ok({
            id: "77777777-7777-4777-8777-777777777777",
            tenant_id: SESSION.scope.tenant_id,
            storage_provider: "LOCAL",
            original_filename: "passport-v2.pdf",
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
      http.post(`*/api/v1/dms/documents/${DOC_ID}/versions`, () => {
        docs[0] = sampleDoc(2);
        return HttpResponse.json(ok(docs[0]));
      }),
      http.post(`*/api/v1/dms/documents/${DOC_ID}/verify-request`, () =>
        HttpResponse.json(ok({ workflow_request_id: "99999999-9999-4999-8999-999999999999" })),
      ),
    );

    seedSession(SESSION);
    seedScope({ tenantId: SESSION.scope.tenant_id, companyId: COMPANY_ID, branchId: BRANCH_ID });
    setSearchParams({ employeeId: EMPLOYEE_ID, docId: DOC_ID });

    renderWithProviders(<EmployeeDocsPage />);

    expect(await screen.findByText("Current version")).toBeVisible();
    expect(await screen.findByText("v1")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Replace document" }));
    await user.upload(
      screen.getByLabelText("File"),
      new File(["y"], "passport-v2.pdf", { type: "application/pdf" })
    );
    await user.click(screen.getByRole("button", { name: /^Replace document$/ }));

    expect(await screen.findByText("v2")).toBeVisible();

    await user.click(screen.getByRole("button", { name: "Request verification" }));
    expect(routerPush).toHaveBeenCalledWith("/workflow/requests/99999999-9999-4999-8999-999999999999");
  }, 60_000);
});
