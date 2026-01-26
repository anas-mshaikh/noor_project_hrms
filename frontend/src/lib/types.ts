/**
 * lib/types.ts
 *
 * Minimal TS types matching your FastAPI response models.
 * We'll keep this small for MVP and expand only as needed.
 */

export type UUID = string;

// ----- Setup -----
export type OrganizationOut = {
  id: UUID;
  name: string;
  created_at: string;
};

export type StoreOut = {
  id: UUID;
  org_id: UUID;
  name: string;
  timezone: string;
  created_at: string;
};

export type CameraListOut = {
  id: UUID;
  store_id: UUID;
  name: string;
  placement: string | null;
  calibration_json: Record<string, unknown> | null;
  created_at: string;
};

// ----- Employees -----
export type EmployeeOut = {
  id: UUID;
  store_id: UUID;
  name: string;
  employee_code: string;
  department: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type FaceCreatedOut = {
  face_id: UUID;
  employee_id: UUID;
  snapshot_path: string;
  model_version: string;
};

// ----- Mobile Accounts (Firebase bootstrap mapping) -----
export type MobileAccountOut = {
  employee_id: UUID;
  employee_code: string;
  firebase_uid: string;
  role: string;
  active: boolean;
  created_at: string;
  revoked_at: string | null;
};

// ----- Videos / Jobs -----
export type VideoInitResponse = {
  video_id: UUID;
  file_path: string;
  upload_endpoint: string; // usually "/api/v1/..."
  finalize_endpoint: string; // usually "/api/v1/..."
};

export type JobCreateResponse = {
  job_id: UUID;
  status: string;
  enqueued: boolean;
  queue_error?: string | null;
};

export type JobReadResponse = {
  id: UUID;
  video_id: UUID;
  status: string;
  progress: number;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

// ----- Results -----
export type AttendanceOut = {
  employee_id: UUID;
  employee_code: string;
  employee_name: string;
  business_date: string;
  punch_in: string | null;
  punch_out: string | null;
  total_minutes: number | null;
  anomalies_json: Record<string, unknown>;
};

export type EventOut = {
  id: UUID;
  ts: string;
  event_type: "entry" | "exit";
  entrance_id: string | null;
  track_key: string;
  employee_id: UUID | null;
  snapshot_path: string | null;
  confidence: number | null;
  is_inferred: boolean;
  meta: Record<string, unknown>;
};

export type MetricsHourlyOut = {
  hour_start_ts: string;
  entries: number;
  exits: number;
  unique_visitors: number;
  avg_dwell_sec: number | null;
};

export type AttendanceDailySummaryOut = {
  business_date: string;
  total_employees: number;
  present_count: number;
  absent_count: number;
  late_count: number;
  avg_worked_minutes: number | null;
  avg_punch_in_minutes: number | null;
};

export type ArtifactOut = {
  id: UUID;
  type: "csv" | "json" | "pdf";
  path: string;
  created_at: string;
};

// ----- HR (Openings + Resume parsing) -----
export type OpeningCreateRequest = {
  title: string;
  jd_text: string;
  requirements_json?: Record<string, unknown>;
};

export type OpeningUpdateRequest = {
  title?: string | null;
  jd_text?: string | null;
  requirements_json?: Record<string, unknown> | null;
  status?: "ACTIVE" | "ARCHIVED" | null;
};

export type OpeningOut = {
  id: UUID;
  store_id: UUID;
  title: string;
  status: "ACTIVE" | "ARCHIVED" | string;
  created_at: string;
  updated_at: string;
};

export type ResumeOut = {
  id: UUID;
  opening_id: UUID;
  store_id: UUID;
  batch_id: UUID | null;
  original_filename: string;
  status: "UPLOADED" | "PARSING" | "PARSED" | "FAILED" | string;
  rq_job_id: string | null;
  error: string | null;
  embedding_status: string;
  embedding_error: string | null;
  embedded_at: string | null;
  created_at: string;
  updated_at: string;
};

export type UploadResumesResponse = {
  batch_id: UUID;
  resume_ids: UUID[];
};

export type BatchStatusOut = {
  batch_id: UUID;
  total_count: number;
  uploaded_count: number;
  parsing_count: number;
  parsed_count: number;
  failed_count: number;
};

// Phase 2: embedding/indexing status for an opening.
export type OpeningIndexStatusOut = {
  opening_id: UUID;
  total_resumes: number;
  parsed_resumes: number;
  parsing_failed: number;
  embedded_resumes: number;
  embedding_failed: number;
};

export type EnqueueOpeningEmbeddingsRequest = {
  resume_ids?: UUID[] | null;
  force?: boolean;
};

export type EnqueueOpeningEmbeddingsResponse = {
  opening_id: UUID;
  enqueued: number;
  skipped: number;
  rq_job_ids: string[];
};

export type ParsedResumeArtifact = {
  resume_id?: UUID;
  clean_text?: string;
  elements?: unknown[];
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
};

// ----- HR (Screening Runs + Results + Explanations) -----
export type ScreeningRunCreateRequest = {
  view_types?: string[] | null;
  k_per_view?: number | null;
  pool_size?: number | null;
  top_n?: number | null;
};

export type ScreeningRunOut = {
  id: UUID;
  opening_id: UUID;
  store_id: UUID;
  status: "QUEUED" | "RUNNING" | "DONE" | "FAILED" | "CANCELLED" | string;
  config_json: Record<string, unknown>;
  model_versions_json: Record<string, unknown>;
  rq_job_id: string | null;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress_total: number;
  progress_done: number;
};

export type ScreeningResultRowOut = {
  rank: number;
  resume_id: UUID;
  original_filename: string;
  resume_status: string;
  embedding_status: string;
  final_score: number;
  rerank_score: number | null;
  retrieval_score: number | null;
  best_view_type: string | null;
};

export type ScreeningResultsPageOut = {
  run_id: UUID;
  status: string;
  page: number;
  page_size: number;
  total_results: number;
  results: ScreeningResultRowOut[];
};

export type ScreeningExplanationOut = {
  run_id: UUID;
  resume_id: UUID;
  rank: number | null;
  model_name: string;
  prompt_version: string;
  explanation_json: Record<string, unknown>;
  created_at: string;
};

export type ScreeningEnqueueResponse = {
  enqueued: boolean;
  rq_job_id: string | null;
};

// ----- HR (ATS / Pipeline) -----

export type PipelineStageOut = {
  id: UUID;
  opening_id: UUID;
  name: string;
  sort_order: number;
  is_terminal: boolean;
  created_at: string;
};

export type PipelineStageUpdateRequest = {
  name?: string | null;
  sort_order?: number | null;
  is_terminal?: boolean | null;
};

export type ResumeMetaOut = {
  id: UUID;
  original_filename: string;
  status: string;
  error: string | null;
};

export type ApplicationOut = {
  id: UUID;
  opening_id: UUID;
  store_id: UUID;
  resume_id: UUID;
  stage_id: UUID | null;
  status: "ACTIVE" | "REJECTED" | "HIRED" | string;
  source_run_id: UUID | null;
  created_at: string;
  updated_at: string;
  resume: ResumeMetaOut;
};

export type CreateApplicationsFromRunRequest = {
  resume_ids?: UUID[] | null;
  top_n?: number | null;
  stage_name?: string | null;
};

export type CreateApplicationsResponse = {
  created_count: number;
  skipped_count: number;
  application_ids: UUID[];
};

export type ApplicationCreateRequest = {
  resume_id: UUID;
  stage_name?: string | null;
};

export type ApplicationUpdateRequest = {
  stage_id?: UUID | null;
  stage_name?: string | null;
};

export type NoteCreateRequest = {
  note: string;
};

export type NoteOut = {
  id: UUID;
  application_id: UUID;
  note: string;
  created_at: string;
};
