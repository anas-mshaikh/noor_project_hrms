import { apiJson, apiForm } from "@/lib/api";
import type {
  BatchStatusOut,
  OpeningCreateRequest,
  OpeningOut,
  OpeningUpdateRequest,
  ParsedResumeArtifact,
  ResumeOut,
  UploadResumesResponse,
  UUID,
} from "@/lib/types";

/**
 * HR Phase‑1 API wrapper (Openings + resume parsing).
 *
 * Notes:
 * - We intentionally reuse `src/lib/api.ts` to keep base URL and error handling consistent.
 * - This module is **framework-agnostic** (no React). Hooks call these functions.
 */

export async function listOpenings(
  storeId: UUID,
  init?: RequestInit
): Promise<OpeningOut[]> {
  return apiJson<OpeningOut[]>(`/api/v1/stores/${storeId}/openings`, init);
}

export async function createOpening(
  storeId: UUID,
  payload: OpeningCreateRequest,
  init?: RequestInit
): Promise<OpeningOut> {
  return apiJson<OpeningOut>(`/api/v1/stores/${storeId}/openings`, {
    method: "POST",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function getOpening(
  openingId: UUID,
  init?: RequestInit
): Promise<OpeningOut> {
  return apiJson<OpeningOut>(`/api/v1/openings/${openingId}`, init);
}

export async function updateOpening(
  openingId: UUID,
  payload: OpeningUpdateRequest,
  init?: RequestInit
): Promise<OpeningOut> {
  return apiJson<OpeningOut>(`/api/v1/openings/${openingId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
    ...init,
  });
}

export async function uploadResumes(
  openingId: UUID,
  files: File[],
  init?: RequestInit
): Promise<UploadResumesResponse> {
  const form = new FormData();
  for (const file of files) {
    // Backend expects repeated field name `files` (UploadFile[]).
    form.append("files", file);
  }

  return apiForm<UploadResumesResponse>(
    `/api/v1/openings/${openingId}/resumes/upload`,
    form,
    init
  );
}

export async function listResumes(
  openingId: UUID,
  statusFilter?: string,
  init?: RequestInit
): Promise<ResumeOut[]> {
  const qs = statusFilter
    ? `?status_filter=${encodeURIComponent(statusFilter)}`
    : "";
  return apiJson<ResumeOut[]>(`/api/v1/openings/${openingId}/resumes${qs}`, init);
}

export async function getBatchStatus(
  openingId: UUID,
  batchId: UUID,
  init?: RequestInit
): Promise<BatchStatusOut> {
  return apiJson<BatchStatusOut>(
    `/api/v1/openings/${openingId}/resumes/batch/${batchId}/status`,
    init
  );
}

export async function getParsedResume(
  resumeId: UUID,
  init?: RequestInit
): Promise<ParsedResumeArtifact> {
  return apiJson<ParsedResumeArtifact>(`/api/v1/resumes/${resumeId}/parsed`, init);
}

