import type { UUID } from "@/lib/types";

/**
 * Centralized React Query keys for the HR module.
 *
 * Why:
 * - Prevents cache fragmentation when multiple pages read/write the same data.
 * - Makes invalidation predictable and easy to audit.
 */
export const hrQueryKeys = {
  openings: (storeId: UUID | null) => ["hr", "openings", storeId] as const,
  opening: (openingId: UUID | null) => ["hr", "opening", openingId] as const,
  resumes: (openingId: UUID | null, statusFilter?: string) =>
    ["hr", "resumes", openingId, statusFilter ?? "ALL"] as const,
  openingIndexStatus: (openingId: UUID | null) =>
    ["hr", "opening-index-status", openingId] as const,
  batchStatus: (openingId: UUID | null, batchId: UUID | null) =>
    ["hr", "batch-status", openingId, batchId] as const,
  parsedResume: (resumeId: UUID | null) => ["hr", "parsed-resume", resumeId] as const,
  screeningRun: (runId: UUID | null) => ["hr", "screening-run", runId] as const,
  screeningResults: (runId: UUID | null, page: number, pageSize: number) =>
    ["hr", "screening-results", runId, page, pageSize] as const,
  screeningExplanation: (runId: UUID | null, resumeId: UUID | null) =>
    ["hr", "screening-explanation", runId, resumeId] as const,
  pipelineStages: (openingId: UUID | null) =>
    ["hr", "pipeline-stages", openingId] as const,
  applications: (openingId: UUID | null) => ["hr", "applications", openingId] as const,
  applicationNotes: (applicationId: UUID | null) =>
    ["hr", "application-notes", applicationId] as const,
};
