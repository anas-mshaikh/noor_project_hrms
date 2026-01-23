"use client";

/**
 * features/hr/mock/types.ts
 *
 * Typed mock models for the HR Suite UI.
 * These are intentionally aligned with backend concepts, but simplified
 * (UI-only, demo-first).
 */

export type HrOpeningStatus = "ACTIVE" | "ARCHIVED";

export type HrOpening = {
  id: string;
  title: string;
  department: string;
  location: string;
  status: HrOpeningStatus;
  created_at: string; // ISO string for demo
  resumes_count: number;
  in_pipeline_count: number;
  last_run_id?: string | null;
};

export type HrResumeParseStatus =
  | "UPLOADED"
  | "PARSING"
  | "PARSED"
  | "FAILED";

export type HrResume = {
  id: string;
  opening_id: string;
  original_filename: string;
  status: HrResumeParseStatus;
  created_at: string;
  error?: string | null;
};

export type HrRunStatus = "QUEUED" | "RUNNING" | "DONE" | "FAILED" | "CANCELLED";

export type HrScreeningRun = {
  id: string;
  opening_id: string;
  title: string;
  status: HrRunStatus;
  created_at: string;
  progress_total: number;
  progress_done: number;
};

export type HrCandidateEvidence = { claim: string; quote: string };

export type HrCandidate = {
  id: string; // resume_id for MVP
  opening_id: string;
  name: string;
  current_title: string;
  score: number; // 0..100
  tags: string[];
  one_line_summary: string;
  matched_requirements: string[];
  missing_requirements: string[];
  strengths: string[];
  risks: string[];
  evidence: HrCandidateEvidence[];
  has_explanation: boolean;
};

export type HrRunResult = {
  run_id: string;
  candidate: HrCandidate;
  rank: number;
  retrieval_score: number;
  rerank_score: number;
};

export type HrPipelineStageKey =
  | "applied"
  | "screened"
  | "interview"
  | "offer"
  | "hired"
  | "rejected";

export type HrPipelineStage = {
  key: HrPipelineStageKey;
  name: string;
  sort_order: number;
  is_terminal: boolean;
};

export type HrPipelineCard = {
  id: string; // candidate/resume id
  stage: HrPipelineStageKey;
  name: string;
  score: number;
  tags: string[];
};

export type HrOnboardingDocStatus = "PENDING" | "UPLOADED" | "VERIFIED" | "REJECTED";

export type HrOnboardingDoc = {
  id: string;
  doc_type: "ID" | "CONTRACT" | "BANK" | "PHOTO";
  status: HrOnboardingDocStatus;
};

export type HrOnboardingTaskStatus = "PENDING" | "DONE" | "BLOCKED";

export type HrOnboardingTask = {
  id: string;
  title: string;
  status: HrOnboardingTaskStatus;
};

export type HrOnboardingEmployee = {
  employee_id: string;
  employee_code: string;
  name: string;
  department: string;
  progress_pct: number; // 0..100
  tasks: HrOnboardingTask[];
  documents: HrOnboardingDoc[];
};

