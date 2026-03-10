import { apiJson } from "@/lib/api";
import type {
  DmsDocumentAddVersionIn,
  DmsDocumentListOut,
  DmsDocumentOut,
  DmsDocumentTypeCreateIn,
  DmsDocumentTypeOut,
  DmsDocumentTypePatchIn,
  DmsDocumentTypesOut,
  DmsEmployeeDocumentCreateIn,
  DmsExpiryRulesOut,
  DmsUpcomingExpiryOut,
  DmsVerifyRequestOut,
  UUID,
} from "@/lib/types";

export async function listDocumentTypes(
  init?: RequestInit,
): Promise<DmsDocumentTypesOut> {
  return apiJson<DmsDocumentTypesOut>("/api/v1/dms/document-types", init);
}

export async function createDocumentType(
  payload: DmsDocumentTypeCreateIn,
  init?: RequestInit,
): Promise<DmsDocumentTypeOut> {
  return apiJson<DmsDocumentTypeOut>("/api/v1/dms/document-types", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function patchDocumentType(
  docTypeId: UUID,
  payload: DmsDocumentTypePatchIn,
  init?: RequestInit,
): Promise<DmsDocumentTypeOut> {
  return apiJson<DmsDocumentTypeOut>(`/api/v1/dms/document-types/${docTypeId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function listEmployeeDocuments(
  args: {
    employeeId: UUID;
    status?: string | null;
    type?: string | null;
    limit: number;
    cursor?: string | null;
  },
  init?: RequestInit,
): Promise<DmsDocumentListOut> {
  const qs = new URLSearchParams({ limit: String(args.limit) });
  if (args.status) qs.set("status", args.status);
  if (args.type) qs.set("type", args.type);
  if (args.cursor) qs.set("cursor", args.cursor);
  return apiJson<DmsDocumentListOut>(
    `/api/v1/hr/employees/${args.employeeId}/documents?${qs.toString()}`,
    init,
  );
}

export async function createEmployeeDocument(
  employeeId: UUID,
  payload: DmsEmployeeDocumentCreateIn,
  init?: RequestInit,
): Promise<DmsDocumentOut> {
  return apiJson<DmsDocumentOut>(`/api/v1/hr/employees/${employeeId}/documents`, {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function addDocumentVersion(
  documentId: UUID,
  payload: DmsDocumentAddVersionIn,
  init?: RequestInit,
): Promise<DmsDocumentOut> {
  return apiJson<DmsDocumentOut>(`/api/v1/dms/documents/${documentId}/versions`, {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function requestDocumentVerification(
  documentId: UUID,
  init?: RequestInit,
): Promise<DmsVerifyRequestOut> {
  return apiJson<DmsVerifyRequestOut>(
    `/api/v1/dms/documents/${documentId}/verify-request`,
    {
      method: "POST",
      ...init,
    },
  );
}

export async function listMyDocuments(
  args: {
    status?: string | null;
    type?: string | null;
    limit: number;
    cursor?: string | null;
  },
  init?: RequestInit,
): Promise<DmsDocumentListOut> {
  const qs = new URLSearchParams({ limit: String(args.limit) });
  if (args.status) qs.set("status", args.status);
  if (args.type) qs.set("type", args.type);
  if (args.cursor) qs.set("cursor", args.cursor);
  return apiJson<DmsDocumentListOut>(`/api/v1/ess/me/documents?${qs.toString()}`, init);
}

export async function getMyDocument(
  documentId: UUID,
  init?: RequestInit,
): Promise<DmsDocumentOut> {
  return apiJson<DmsDocumentOut>(`/api/v1/ess/me/documents/${documentId}`, init);
}

export async function listExpiryRules(
  init?: RequestInit,
): Promise<DmsExpiryRulesOut> {
  return apiJson<DmsExpiryRulesOut>("/api/v1/dms/expiry/rules", init);
}

export async function listUpcomingExpiry(
  days: number,
  init?: RequestInit,
): Promise<DmsUpcomingExpiryOut> {
  return apiJson<DmsUpcomingExpiryOut>(`/api/v1/dms/expiry/upcoming?days=${days}`, init);
}
