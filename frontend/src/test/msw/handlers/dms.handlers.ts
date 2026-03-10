import { http, HttpResponse } from "msw";

import { fail, ok } from "@/test/msw/builders/response";

const DEFAULT_FILE_ID = "00000000-0000-4000-8000-000000000001";
const DEFAULT_DOC_ID = "10000000-0000-4000-8000-000000000001";
const DEFAULT_DOC_TYPE_ID = "20000000-0000-4000-8000-000000000001";
const DEFAULT_EMPLOYEE_ID = "30000000-0000-4000-8000-000000000001";
const DEFAULT_WORKFLOW_ID = "40000000-0000-4000-8000-000000000001";

function sampleFile(id: string) {
  const now = new Date(0).toISOString();
  return {
    id,
    tenant_id: "t-1",
    storage_provider: "LOCAL",
    original_filename: "attachment.bin",
    content_type: "application/octet-stream",
    size_bytes: 1,
    sha256: null,
    status: "READY",
    created_by_user_id: null,
    created_at: now,
    updated_at: now,
    meta: null,
  };
}

function sampleDocType(id = DEFAULT_DOC_TYPE_ID) {
  const now = new Date(0).toISOString();
  return {
    id,
    tenant_id: "t-1",
    code: "PASSPORT",
    name: "Passport",
    requires_expiry: true,
    is_active: true,
    created_at: now,
    updated_at: now,
  };
}

function sampleDocument(id = DEFAULT_DOC_ID) {
  const now = new Date(0).toISOString();
  return {
    id,
    tenant_id: "t-1",
    document_type_id: DEFAULT_DOC_TYPE_ID,
    document_type_code: "PASSPORT",
    document_type_name: "Passport",
    owner_employee_id: DEFAULT_EMPLOYEE_ID,
    status: "SUBMITTED",
    expires_at: "2026-12-31",
    current_version_id: "50000000-0000-4000-8000-000000000001",
    current_version: {
      id: "50000000-0000-4000-8000-000000000001",
      tenant_id: "t-1",
      document_id: id,
      file_id: DEFAULT_FILE_ID,
      version: 1,
      notes: null,
      created_by_user_id: null,
      created_at: now,
    },
    verified_at: null,
    verified_by_user_id: null,
    rejected_reason: null,
    created_by_user_id: null,
    verification_workflow_request_id: DEFAULT_WORKFLOW_ID,
    created_at: now,
    updated_at: now,
    meta: null,
  };
}

export const dmsHandlers = [
  http.get("*/api/v1/dms/document-types", () =>
    HttpResponse.json(ok({ items: [] })),
  ),

  http.post("*/api/v1/dms/document-types", async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...sampleDocType(),
        code: String(body.code ?? "PASSPORT"),
        name: String(body.name ?? "Passport"),
        requires_expiry: Boolean(body.requires_expiry ?? false),
        is_active: Boolean(body.is_active ?? true),
      }),
    );
  }),

  http.patch("*/api/v1/dms/document-types/:docTypeId", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...sampleDocType(String(params.docTypeId)),
        name: String(body.name ?? "Passport"),
        requires_expiry: body.requires_expiry == null ? true : Boolean(body.requires_expiry),
        is_active: body.is_active == null ? true : Boolean(body.is_active),
      }),
    );
  }),

  http.get("*/api/v1/hr/employees/:employeeId/documents", () =>
    HttpResponse.json(ok({ items: [], next_cursor: null })),
  ),

  http.post("*/api/v1/hr/employees/:employeeId/documents", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...sampleDocument(),
        owner_employee_id: String(params.employeeId),
        document_type_code: String(body.document_type_code ?? "PASSPORT"),
        expires_at: body.expires_at ? String(body.expires_at) : null,
      }),
    );
  }),

  http.post("*/api/v1/dms/documents/:documentId/versions", async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json(
      ok({
        ...sampleDocument(String(params.documentId)),
        current_version: {
          ...sampleDocument(String(params.documentId)).current_version,
          file_id: String(body.file_id ?? DEFAULT_FILE_ID),
          version: 2,
          notes: body.notes ? String(body.notes) : null,
        },
      }),
    );
  }),

  http.post("*/api/v1/dms/documents/:documentId/verify-request", ({ params }) =>
    HttpResponse.json(
      ok({
        workflow_request_id: params.documentId === DEFAULT_DOC_ID ? DEFAULT_WORKFLOW_ID : "40000000-0000-4000-8000-000000000002",
      }),
    ),
  ),

  http.get("*/api/v1/ess/me/documents", () =>
    HttpResponse.json(ok({ items: [], next_cursor: null })),
  ),

  http.get("*/api/v1/ess/me/documents/:documentId", ({ params }) => {
    if (String(params.documentId) === DEFAULT_DOC_ID) {
      return HttpResponse.json(ok(sampleDocument(String(params.documentId))));
    }
    return HttpResponse.json(
      fail("dms.document.not_found", "Document not found", { correlation_id: "cid-dms-not-found" }),
      { status: 404 },
    );
  }),

  http.get("*/api/v1/dms/expiry/rules", () =>
    HttpResponse.json(ok({ items: [] })),
  ),

  http.get("*/api/v1/dms/expiry/upcoming", () =>
    HttpResponse.json(ok({ items: [] })),
  ),

  http.post("*/api/v1/dms/files", () =>
    HttpResponse.json(ok(sampleFile(DEFAULT_FILE_ID))),
  ),

  http.get("*/api/v1/dms/files/:fileId", ({ params }) => {
    const fileId = String(params.fileId);
    return HttpResponse.json(ok(sampleFile(fileId)));
  }),

  http.get("*/api/v1/dms/files/:fileId/download", ({ params }) => {
    const fileId = String(params.fileId);
    return new HttpResponse(new Uint8Array([1, 2, 3]), {
      status: 200,
      headers: {
        "Content-Type": "application/octet-stream",
        "Content-Disposition": `attachment; filename="${fileId}.bin"`,
      },
    });
  }),
];
