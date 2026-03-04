/**
 * lib/types.ts
 *
 * Minimal TS types matching your FastAPI response models.
 * We'll keep this small for MVP and expand only as needed.
 */

export type UUID = string;

// ----- Auth -----
export type UserOut = {
  id: UUID;
  email: string;
  status: string;
};

export type ScopeOut = {
  tenant_id: UUID;
  company_id: UUID | null;
  branch_id: UUID | null;
  allowed_tenant_ids: UUID[];
  allowed_company_ids: UUID[];
  allowed_branch_ids: UUID[];
};

export type TokenResponse = {
  access_token: string;
  refresh_token: string;
  user: UserOut;
  roles: string[];
  permissions: string[];
  scope: ScopeOut;
};

export type MeResponse = {
  user: UserOut;
  roles: string[];
  permissions: string[];
  scope: ScopeOut;
};

// ----- Tenancy (vNext masters) -----
export type CompanyCreate = {
  name: string;
  legal_name?: string | null;
  currency_code?: string | null;
  timezone?: string | null;
};

export type CompanyOut = {
  id: UUID;
  tenant_id: UUID;
  name: string;
  legal_name: string | null;
  currency_code: string | null;
  timezone: string | null;
  status: string;
};

export type BranchCreate = {
  company_id: UUID;
  name: string;
  code: string;
  timezone?: string | null;
  address?: Record<string, unknown>;
};

export type BranchOut = {
  id: UUID;
  tenant_id: UUID;
  company_id: UUID;
  name: string;
  code: string;
  timezone: string | null;
  address: Record<string, unknown>;
  status: string;
};

export type OrgUnitCreate = {
  company_id: UUID;
  branch_id?: UUID | null;
  parent_id?: UUID | null;
  name: string;
  unit_type?: string | null;
};

export type OrgUnitOut = {
  id: UUID;
  tenant_id: UUID;
  company_id: UUID;
  branch_id: UUID | null;
  parent_id: UUID | null;
  name: string;
  unit_type: string | null;
};

export type OrgUnitNode = {
  id: UUID;
  name: string;
  unit_type: string | null;
  children: OrgUnitNode[];
};

export type JobTitleCreate = {
  company_id: UUID;
  name: string;
};

export type JobTitleOut = {
  id: UUID;
  tenant_id: UUID;
  company_id: UUID;
  name: string;
};

export type GradeCreate = {
  company_id: UUID;
  name: string;
  level?: number | null;
};

export type GradeOut = {
  id: UUID;
  tenant_id: UUID;
  company_id: UUID;
  name: string;
  level: number | null;
};

export type CameraListOut = {
  id: UUID;
  tenant_id: UUID;
  branch_id: UUID;
  name: string;
  placement: string | null;
  calibration_json: Record<string, unknown> | null;
  created_at: string;
};

// ----- IAM -----
export type UsersListMeta = {
  limit: number;
  offset: number;
  total: number;
};

export type IamUserStatus = "ACTIVE" | "DISABLED" | string;

export type IamUserOut = {
  id: UUID;
  email: string;
  phone: string | null;
  status: IamUserStatus;
  created_at: string;
};

export type IamUserCreateIn = {
  email: string;
  phone?: string | null;
  password: string;
  status?: "ACTIVE" | "DISABLED";
};

export type IamUserPatchIn = {
  phone?: string | null;
  status?: "ACTIVE" | "DISABLED" | null;
};

export type IamRoleAssignIn = {
  role_code: string;
  tenant_id?: UUID | null;
  company_id?: UUID | null;
  branch_id?: UUID | null;
};

export type UserRoleOut = {
  role_code: string;
  tenant_id: UUID;
  company_id: UUID | null;
  branch_id: UUID | null;
  created_at: string;
};

export type RoleOut = {
  code: string;
  name: string;
  description: string | null;
};

export type PermissionOut = {
  code: string;
  description: string | null;
};

// ----- HR (canonical employee directory) -----
export type EmployeeDirectoryRowOut = {
  employee_id: UUID;
  employee_code: string;
  status: string;
  full_name: string;
  email: string | null;
  phone: string | null;
  branch_id: UUID | null;
  org_unit_id: UUID | null;
  manager_employee_id: UUID | null;
  manager_name: string | null;
  has_user_link?: boolean;
};

export type EmployeeDirectoryListOut = {
  items: EmployeeDirectoryRowOut[];
  paging: { limit: number; offset: number; total: number };
};

export type HrManagerSummaryOut = {
  employee_id: UUID;
  display_name: string;
  employee_code: string | null;
};

export type HrPersonOut = {
  id: UUID;
  tenant_id: UUID;
  first_name: string;
  last_name: string;
  dob: string | null;
  nationality: string | null;
  email: string | null;
  phone: string | null;
  address: Record<string, unknown>;
  created_at: string;
  updated_at: string;
};

export type HrEmployeeOut = {
  id: UUID;
  tenant_id: UUID;
  company_id: UUID;
  person_id: UUID;
  employee_code: string;
  status: string;
  join_date: string | null;
  termination_date: string | null;
  created_at: string;
  updated_at: string;
};

export type HrEmploymentOut = {
  id: UUID;
  tenant_id: UUID;
  company_id: UUID;
  employee_id: UUID;
  branch_id: UUID;
  org_unit_id: UUID | null;
  job_title_id: UUID | null;
  grade_id: UUID | null;
  manager_employee_id: UUID | null;
  start_date: string;
  end_date: string | null;
  is_primary: boolean | null;
  created_at: string;
  updated_at: string;
};

export type HrLinkedUserOut = {
  user_id: UUID;
  email: string;
  status: string;
  linked_at: string;
};

export type HrEmployee360Out = {
  employee: HrEmployeeOut;
  person: HrPersonOut;
  current_employment: HrEmploymentOut | null;
  manager: HrManagerSummaryOut | null;
  linked_user: HrLinkedUserOut | null;
};

export type HrEmployeeCreateIn = {
  person: {
    first_name: string;
    last_name: string;
    dob?: string | null;
    nationality?: string | null;
    email?: string | null;
    phone?: string | null;
    address: Record<string, unknown>;
  };
  employee: {
    company_id: UUID;
    employee_code: string;
    join_date?: string | null;
    status?: "ACTIVE" | "INACTIVE" | "TERMINATED" | string;
  };
  employment: {
    start_date: string;
    branch_id: UUID;
    org_unit_id?: UUID | null;
    job_title_id?: UUID | null;
    grade_id?: UUID | null;
    manager_employee_id?: UUID | null;
    is_primary: boolean;
  };
};

export type HrEmploymentChangeIn = {
  start_date: string;
  branch_id: UUID;
  org_unit_id?: UUID | null;
  job_title_id?: UUID | null;
  grade_id?: UUID | null;
  manager_employee_id?: UUID | null;
};

export type HrEmployeeLinkUserIn = {
  user_id: UUID;
};

export type HrEmployeeUserLinkOut = {
  employee_id: UUID;
  user_id: UUID;
  created_at: string;
};

export type EssProfilePatchIn = {
  email?: string | null;
  phone?: string | null;
  address?: Record<string, unknown> | null;
};

export type PagingOut = {
  limit: number;
  offset: number;
  total: number;
};

export type MssEmployeeSummaryOut = {
  employee_id: UUID;
  employee_code: string;
  display_name: string;
  status: string;
  branch_id: UUID | null;
  org_unit_id: UUID | null;
  job_title_id: UUID | null;
  grade_id: UUID | null;
  manager_employee_id: UUID | null;
  relationship_depth: number;
};

export type MssTeamListOut = {
  items: MssEmployeeSummaryOut[];
  paging: PagingOut;
};

export type MssPersonOut = {
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
};

export type MssEmployeeOut = {
  id: UUID;
  employee_code: string;
  status: string;
  join_date: string | null;
  termination_date: string | null;
};

export type MssEmploymentOut = {
  branch_id: UUID;
  org_unit_id: UUID | null;
  job_title_id: UUID | null;
  grade_id: UUID | null;
  manager_employee_id: UUID | null;
};

export type MssEmployeeProfileOut = {
  employee: MssEmployeeOut;
  person: MssPersonOut;
  current_employment: MssEmploymentOut | null;
  manager: HrManagerSummaryOut | null;
};

// Face system endpoints intentionally return file paths + ids only.
export type FaceRegisterOut = {
  employee_id: UUID;
  stored: { filename: string; rel_path: string };
};

export type FaceRecognizeOut = {
  employee_id: UUID | null;
  confidence: number;
  cosine_similarity: number | null;
  top_k: Array<{
    employee_id: UUID;
    cosine_similarity: number;
    confidence: number;
  }>;
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
  tenant_id: UUID;
  company_id: UUID;
  branch_id: UUID;
  title: string;
  status: "ACTIVE" | "ARCHIVED" | string;
  created_at: string;
  updated_at: string;
};

export type ResumeOut = {
  id: UUID;
  opening_id: UUID;
  tenant_id: UUID;
  company_id: UUID;
  branch_id: UUID;
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
  tenant_id: UUID;
  company_id: UUID;
  branch_id: UUID;
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
  tenant_id: UUID;
  company_id: UUID;
  branch_id: UUID;
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
