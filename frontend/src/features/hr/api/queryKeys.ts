import type { UUID } from "@/lib/types";

/**
 * Centralized React Query keys for the HR module.
 *
 * Why:
 * - Prevents cache fragmentation when multiple pages read/write the same data.
 * - Makes invalidation predictable and easy to audit.
 */
export const hrQueryKeys = {
  openings: (branchId: UUID | null) => ["hr", "openings", branchId] as const,
  opening: (branchId: UUID | null, openingId: UUID | null) =>
    ["hr", "opening", branchId, openingId] as const,
  resumes: (branchId: UUID | null, openingId: UUID | null, statusFilter?: string) =>
    ["hr", "resumes", branchId, openingId, statusFilter ?? "ALL"] as const,
  openingIndexStatus: (branchId: UUID | null, openingId: UUID | null) =>
    ["hr", "opening-index-status", branchId, openingId] as const,
  batchStatus: (branchId: UUID | null, openingId: UUID | null, batchId: UUID | null) =>
    ["hr", "batch-status", branchId, openingId, batchId] as const,
  parsedResume: (branchId: UUID | null, resumeId: UUID | null) =>
    ["hr", "parsed-resume", branchId, resumeId] as const,
  screeningRun: (branchId: UUID | null, runId: UUID | null) =>
    ["hr", "screening-run", branchId, runId] as const,
  screeningResults: (branchId: UUID | null, runId: UUID | null, page: number, pageSize: number) =>
    ["hr", "screening-results", branchId, runId, page, pageSize] as const,
  screeningExplanation: (branchId: UUID | null, runId: UUID | null, resumeId: UUID | null) =>
    ["hr", "screening-explanation", branchId, runId, resumeId] as const,
  pipelineStages: (branchId: UUID | null, openingId: UUID | null) =>
    ["hr", "pipeline-stages", branchId, openingId] as const,
  applications: (branchId: UUID | null, openingId: UUID | null) =>
    ["hr", "applications", branchId, openingId] as const,
  applicationNotes: (branchId: UUID | null, applicationId: UUID | null) =>
    ["hr", "application-notes", branchId, applicationId] as const,
};
