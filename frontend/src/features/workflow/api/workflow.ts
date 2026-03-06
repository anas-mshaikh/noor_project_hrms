import { apiJson } from "@/lib/api";
import type {
  UUID,
  WorkflowAttachmentCreateIn,
  WorkflowCommentCreateIn,
  WorkflowDefinitionCreateIn,
  WorkflowDefinitionOut,
  WorkflowDefinitionStepsIn,
  WorkflowRequestActionOut,
  WorkflowRequestApproveIn,
  WorkflowRequestCreateIn,
  WorkflowRequestDetailOut,
  WorkflowRequestListOut,
  WorkflowRequestRejectIn,
  WorkflowRequestSummaryOut,
} from "@/lib/types";

/**
 * Workflow API wrapper (Inbox/Outbox/Requests/Definitions).
 *
 * Notes:
 * - Pure functions only (no React).
 * - Pagination uses cursor + next_cursor; UI should implement "Load more".
 */

export async function createRequest(
  payload: WorkflowRequestCreateIn,
  init?: RequestInit,
): Promise<WorkflowRequestSummaryOut> {
  return apiJson<WorkflowRequestSummaryOut>("/api/v1/workflow/requests", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function getRequest(
  requestId: UUID,
  init?: RequestInit,
): Promise<WorkflowRequestDetailOut> {
  return apiJson<WorkflowRequestDetailOut>(
    `/api/v1/workflow/requests/${requestId}`,
    init,
  );
}

export async function listInbox(
  args: {
    status?: "pending" | "submitted" | string;
    limit: number;
    cursor?: string | null;
    type?: string | null;
    companyId?: UUID | null;
    branchId?: UUID | null;
  },
  init?: RequestInit,
): Promise<WorkflowRequestListOut> {
  const qs = new URLSearchParams({
    status: args.status ?? "pending",
    limit: String(args.limit),
  });
  if (args.cursor) qs.set("cursor", args.cursor);
  if (args.type) qs.set("type", args.type);
  if (args.companyId) qs.set("company_id", args.companyId);
  if (args.branchId) qs.set("branch_id", args.branchId);

  return apiJson<WorkflowRequestListOut>(
    `/api/v1/workflow/inbox?${qs.toString()}`,
    init,
  );
}

export async function listOutbox(
  args: {
    status?: string | null;
    limit: number;
    cursor?: string | null;
    type?: string | null;
  },
  init?: RequestInit,
): Promise<WorkflowRequestListOut> {
  const qs = new URLSearchParams({
    limit: String(args.limit),
  });
  if (args.status) qs.set("status", args.status);
  if (args.cursor) qs.set("cursor", args.cursor);
  if (args.type) qs.set("type", args.type);

  return apiJson<WorkflowRequestListOut>(
    `/api/v1/workflow/outbox?${qs.toString()}`,
    init,
  );
}

export async function cancelRequest(
  requestId: UUID,
  init?: RequestInit,
): Promise<WorkflowRequestActionOut> {
  return apiJson<WorkflowRequestActionOut>(
    `/api/v1/workflow/requests/${requestId}/cancel`,
    {
      method: "POST",
      ...init,
    },
  );
}

export async function approveRequest(
  requestId: UUID,
  payload: WorkflowRequestApproveIn,
  init?: RequestInit,
): Promise<WorkflowRequestActionOut> {
  return apiJson<WorkflowRequestActionOut>(
    `/api/v1/workflow/requests/${requestId}/approve`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      ...init,
    },
  );
}

export async function rejectRequest(
  requestId: UUID,
  payload: WorkflowRequestRejectIn,
  init?: RequestInit,
): Promise<WorkflowRequestActionOut> {
  return apiJson<WorkflowRequestActionOut>(
    `/api/v1/workflow/requests/${requestId}/reject`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      ...init,
    },
  );
}

export async function addComment(
  requestId: UUID,
  payload: WorkflowCommentCreateIn,
  init?: RequestInit,
): Promise<{ id: string; created_at: string }> {
  return apiJson<{ id: string; created_at: string }>(
    `/api/v1/workflow/requests/${requestId}/comments`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      ...init,
    },
  );
}

export async function addAttachment(
  requestId: UUID,
  payload: WorkflowAttachmentCreateIn,
  init?: RequestInit,
): Promise<{ id: string; created_at: string }> {
  return apiJson<{ id: string; created_at: string }>(
    `/api/v1/workflow/requests/${requestId}/attachments`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      ...init,
    },
  );
}

export async function listDefinitions(
  args?: { companyId?: UUID | null },
  init?: RequestInit,
): Promise<WorkflowDefinitionOut[]> {
  const qs = new URLSearchParams();
  if (args?.companyId) qs.set("company_id", args.companyId);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiJson<WorkflowDefinitionOut[]>(
    `/api/v1/workflow/definitions${suffix}`,
    init,
  );
}

export async function createDefinition(
  payload: WorkflowDefinitionCreateIn,
  init?: RequestInit,
): Promise<WorkflowDefinitionOut> {
  return apiJson<WorkflowDefinitionOut>("/api/v1/workflow/definitions", {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function replaceDefinitionSteps(
  definitionId: UUID,
  payload: WorkflowDefinitionStepsIn,
  init?: RequestInit,
): Promise<{ updated: boolean }> {
  return apiJson<{ updated: boolean }>(
    `/api/v1/workflow/definitions/${definitionId}/steps`,
    {
      method: "POST",
      body: JSON.stringify(payload),
      ...init,
    },
  );
}

export async function activateDefinition(
  definitionId: UUID,
  init?: RequestInit,
): Promise<{ activated: boolean }> {
  return apiJson<{ activated: boolean }>(
    `/api/v1/workflow/definitions/${definitionId}/activate`,
    {
      method: "POST",
      ...init,
    },
  );
}
