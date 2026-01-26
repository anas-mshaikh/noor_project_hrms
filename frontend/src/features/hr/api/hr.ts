import { apiJson, apiForm } from "@/lib/api";
import type {
  ApplicationCreateRequest,
  ApplicationOut,
  ApplicationUpdateRequest,
  BatchStatusOut,
  CreateApplicationsFromRunRequest,
  CreateApplicationsResponse,
  EnqueueOpeningEmbeddingsRequest,
  EnqueueOpeningEmbeddingsResponse,
  NoteCreateRequest,
  NoteOut,
  OpeningIndexStatusOut,
  OpeningCreateRequest,
  OpeningOut,
  OpeningUpdateRequest,
  ParsedResumeArtifact,
  PipelineStageOut,
  PipelineStageUpdateRequest,
  ResumeOut,
  ScreeningEnqueueResponse,
  ScreeningExplanationOut,
  ScreeningResultsPageOut,
  ScreeningRunCreateRequest,
  ScreeningRunOut,
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

export async function getOpeningIndexStatus(
  openingId: UUID,
  init?: RequestInit
): Promise<OpeningIndexStatusOut> {
  return apiJson<OpeningIndexStatusOut>(
    `/api/v1/openings/${openingId}/resumes/index-status`,
    init
  );
}

export async function enqueueOpeningEmbeddings(
  openingId: UUID,
  payload: EnqueueOpeningEmbeddingsRequest,
  init?: RequestInit
): Promise<EnqueueOpeningEmbeddingsResponse> {
  return apiJson<EnqueueOpeningEmbeddingsResponse>(
    `/api/v1/openings/${openingId}/resumes/embed`,
    {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
      ...init,
    }
  );
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

// ------------------------------------------------------------
// HR Phase 3/4: Screening Runs + Results + Explanations
// ------------------------------------------------------------

export async function createScreeningRun(
  openingId: UUID,
  payload: ScreeningRunCreateRequest,
  init?: RequestInit
): Promise<ScreeningRunOut> {
  return apiJson<ScreeningRunOut>(`/api/v1/openings/${openingId}/screening-runs`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
    ...init,
  });
}

export async function getScreeningRun(
  runId: UUID,
  init?: RequestInit
): Promise<ScreeningRunOut> {
  return apiJson<ScreeningRunOut>(`/api/v1/screening-runs/${runId}`, init);
}

export async function cancelScreeningRun(
  runId: UUID,
  init?: RequestInit
): Promise<ScreeningRunOut> {
  return apiJson<ScreeningRunOut>(`/api/v1/screening-runs/${runId}/cancel`, {
    method: "POST",
    body: JSON.stringify({}),
    ...init,
  });
}

export async function retryScreeningRun(
  runId: UUID,
  init?: RequestInit
): Promise<ScreeningRunOut> {
  return apiJson<ScreeningRunOut>(`/api/v1/screening-runs/${runId}/retry`, {
    method: "POST",
    body: JSON.stringify({}),
    ...init,
  });
}

export async function listScreeningResults(
  runId: UUID,
  args?: { page?: number; pageSize?: number },
  init?: RequestInit
): Promise<ScreeningResultsPageOut> {
  const page = args?.page ?? 1;
  const pageSize = args?.pageSize ?? 50;
  const qs = `?page=${encodeURIComponent(page)}&page_size=${encodeURIComponent(
    pageSize
  )}`;
  return apiJson<ScreeningResultsPageOut>(
    `/api/v1/screening-runs/${runId}/results${qs}`,
    init
  );
}

export async function getScreeningExplanation(
  runId: UUID,
  resumeId: UUID,
  init?: RequestInit
): Promise<ScreeningExplanationOut> {
  return apiJson<ScreeningExplanationOut>(
    `/api/v1/screening-runs/${runId}/results/${resumeId}/explanation`,
    init
  );
}

export async function enqueueRunExplanations(
  runId: UUID,
  args?: { topN?: number; force?: boolean },
  init?: RequestInit
): Promise<ScreeningEnqueueResponse> {
  return apiJson<ScreeningEnqueueResponse>(
    `/api/v1/screening-runs/${runId}/explanations`,
    {
      method: "POST",
      body: JSON.stringify({
        top_n: args?.topN ?? null,
        force: Boolean(args?.force ?? false),
      }),
      ...init,
    }
  );
}

export async function recomputeSingleExplanation(
  runId: UUID,
  resumeId: UUID,
  args?: { force?: boolean },
  init?: RequestInit
): Promise<ScreeningEnqueueResponse> {
  return apiJson<ScreeningEnqueueResponse>(
    `/api/v1/screening-runs/${runId}/results/${resumeId}/explanation/recompute`,
    {
      method: "POST",
      body: JSON.stringify({
        force: Boolean(args?.force ?? true),
      }),
      ...init,
    }
  );
}

// ------------------------------------------------------------
// HR Phase 5: ATS (Pipeline + Applications + Notes)
// ------------------------------------------------------------

export async function listPipelineStages(
  openingId: UUID,
  init?: RequestInit
): Promise<PipelineStageOut[]> {
  return apiJson<PipelineStageOut[]>(
    `/api/v1/openings/${openingId}/pipeline-stages`,
    init
  );
}

export async function updatePipelineStage(
  openingId: UUID,
  stageId: UUID,
  payload: PipelineStageUpdateRequest,
  init?: RequestInit
): Promise<PipelineStageOut> {
  return apiJson<PipelineStageOut>(
    `/api/v1/openings/${openingId}/pipeline-stages/${stageId}`,
    {
      method: "PATCH",
      body: JSON.stringify(payload ?? {}),
      ...init,
    }
  );
}

export async function createApplicationsFromRun(
  runId: UUID,
  payload: CreateApplicationsFromRunRequest,
  init?: RequestInit
): Promise<CreateApplicationsResponse> {
  return apiJson<CreateApplicationsResponse>(
    `/api/v1/screening-runs/${runId}/applications`,
    {
      method: "POST",
      body: JSON.stringify(payload ?? {}),
      ...init,
    }
  );
}

export async function createApplication(
  openingId: UUID,
  payload: ApplicationCreateRequest,
  init?: RequestInit
): Promise<ApplicationOut> {
  return apiJson<ApplicationOut>(`/api/v1/openings/${openingId}/applications`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
    ...init,
  });
}

export async function listApplications(
  openingId: UUID,
  args?: { stageId?: UUID | null; status?: string | null },
  init?: RequestInit
): Promise<ApplicationOut[]> {
  const qs = new URLSearchParams();
  if (args?.stageId) qs.set("stage_id", String(args.stageId));
  if (args?.status) qs.set("status", String(args.status));
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  return apiJson<ApplicationOut[]>(
    `/api/v1/openings/${openingId}/applications${suffix}`,
    init
  );
}

export async function updateApplication(
  applicationId: UUID,
  payload: ApplicationUpdateRequest,
  init?: RequestInit
): Promise<ApplicationOut> {
  return apiJson<ApplicationOut>(`/api/v1/applications/${applicationId}`, {
    method: "PATCH",
    body: JSON.stringify(payload ?? {}),
    ...init,
  });
}

export async function rejectApplication(
  applicationId: UUID,
  init?: RequestInit
): Promise<ApplicationOut> {
  return apiJson<ApplicationOut>(
    `/api/v1/applications/${applicationId}/reject`,
    {
      method: "POST",
      body: JSON.stringify({}),
      ...init,
    }
  );
}

export async function hireApplication(
  applicationId: UUID,
  init?: RequestInit
): Promise<ApplicationOut> {
  return apiJson<ApplicationOut>(`/api/v1/applications/${applicationId}/hire`, {
    method: "POST",
    body: JSON.stringify({}),
    ...init,
  });
}

export async function listApplicationNotes(
  applicationId: UUID,
  init?: RequestInit
): Promise<NoteOut[]> {
  return apiJson<NoteOut[]>(`/api/v1/applications/${applicationId}/notes`, init);
}

export async function createApplicationNote(
  applicationId: UUID,
  payload: NoteCreateRequest,
  init?: RequestInit
): Promise<NoteOut> {
  return apiJson<NoteOut>(`/api/v1/applications/${applicationId}/notes`, {
    method: "POST",
    body: JSON.stringify(payload ?? {}),
    ...init,
  });
}
