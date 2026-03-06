import { http, HttpResponse } from "msw";

import { ok } from "@/test/msw/builders/response";

const DEFAULT_FILE_ID = "00000000-0000-4000-8000-000000000001";

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

/**
 * DMS handlers (safe defaults).
 *
 * Individual tests should override with `server.use(...)` as needed.
 */
export const dmsHandlers = [
  http.post("*/api/v1/dms/files", () =>
    HttpResponse.json(ok(sampleFile(DEFAULT_FILE_ID))),
  ),

  http.get("*/api/v1/dms/files/:fileId", ({ params }) => {
    const fileId = String(params.fileId);
    return HttpResponse.json(ok(sampleFile(fileId)));
  }),
];
