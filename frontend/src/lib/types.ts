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

// ----- Attendance (ESS/MSS) -----
export type PunchStateOut = {
  today_business_date: string; // YYYY-MM-DD
  is_punched_in: boolean;
  open_session_started_at: string | null;
  base_minutes_today: number;
  effective_minutes_today: number;
  effective_status_today: string;
};

export type AttendanceDayOverrideOut = {
  kind: string; // "LEAVE" | "CORRECTION"
  status: string;
  source_type: string;
  source_id: UUID;
};

export type AttendanceDayOut = {
  day: string; // YYYY-MM-DD
  base_status: string;
  effective_status: string;
  base_minutes: number;
  effective_minutes: number;
  first_in: string | null;
  last_out: string | null;
  has_open_session: boolean;
  sources: string[];
  override: AttendanceDayOverrideOut | null;
};

export type AttendanceDaysOut = {
  items: AttendanceDayOut[];
};

export type AttendanceCorrectionCreateIn = {
  day: string; // YYYY-MM-DD
  correction_type: string;
  requested_override_status: string;
  reason?: string | null;
  evidence_file_ids?: UUID[];
  idempotency_key?: string | null;
};

export type AttendanceCorrectionOut = {
  id: UUID;
  tenant_id: UUID;
  employee_id: UUID;
  branch_id: UUID;
  day: string; // YYYY-MM-DD
  correction_type: string;
  requested_override_status: string;
  reason: string | null;
  evidence_file_ids: UUID[];
  status: string;
  workflow_request_id: UUID | null;
  idempotency_key: string | null;
  created_at: string;
  updated_at: string;
  meta?: Record<string, unknown> | null;
};

export type AttendanceCorrectionListOut = {
  items: AttendanceCorrectionOut[];
  next_cursor: string | null;
};

// ----- Leave (ESS/MSS) -----
export type LeaveBalanceOut = {
  leave_type_code: string;
  leave_type_name: string;
  period_year: number;
  balance_days: number;
  used_days: number;
  pending_days: number;
};

export type LeaveBalancesOut = {
  items: LeaveBalanceOut[];
};

export type LeaveRequestCreateIn = {
  leave_type_code: string;
  start_date: string; // YYYY-MM-DD
  end_date: string; // YYYY-MM-DD
  unit?: "DAY" | "HALF_DAY" | string;
  half_day_part?: "AM" | "PM" | string | null;
  reason?: string | null;
  attachment_file_ids?: UUID[];
  idempotency_key?: string | null;
};

export type LeaveRequestOut = {
  id: UUID;
  tenant_id: UUID;
  employee_id: UUID;
  company_id: UUID | null;
  branch_id: UUID | null;
  leave_type_code: string;
  leave_type_name: string | null;
  policy_id: UUID;
  start_date: string; // YYYY-MM-DD
  end_date: string; // YYYY-MM-DD
  unit: string;
  half_day_part: string | null;
  requested_days: number;
  reason: string | null;
  status: string;
  workflow_request_id: UUID | null;
  created_at: string;
  updated_at: string;
};

export type LeaveRequestListOut = {
  items: LeaveRequestOut[];
  next_cursor: string | null;
};

export type TeamLeaveSpanOut = {
  leave_request_id: UUID;
  employee_id: UUID;
  start_date: string; // YYYY-MM-DD
  end_date: string; // YYYY-MM-DD
  leave_type_code: string;
  requested_days: number;
};

export type TeamCalendarOut = {
  items: TeamLeaveSpanOut[];
};

// ----- Workflow (backbone) -----
export type WorkflowRequestCreateIn = {
  request_type_code: string;
  payload: Record<string, unknown>;
  subject_employee_id?: UUID | null;
  entity_type?: string | null;
  entity_id?: UUID | null;
  company_id?: UUID | null;
  branch_id?: UUID | null;
  idempotency_key?: string | null;
  comment?: string | null;
};

export type WorkflowRequestApproveIn = {
  comment?: string | null;
};

export type WorkflowRequestRejectIn = {
  comment: string;
};

export type WorkflowCommentCreateIn = {
  body: string;
};

export type WorkflowAttachmentCreateIn = {
  file_id: UUID;
  note?: string | null;
};

export type WorkflowRequestSummaryOut = {
  id: UUID;
  request_type_code: string;
  status: string;
  current_step: number;
  subject: string | null;
  payload: Record<string, unknown> | null;
  tenant_id: UUID;
  company_id: UUID;
  branch_id: UUID | null;
  created_by_user_id: UUID | null;
  requester_employee_id: UUID;
  subject_employee_id: UUID | null;
  entity_type: string | null;
  entity_id: UUID | null;
  created_at: string;
  updated_at: string;
};

export type WorkflowRequestListOut = {
  items: WorkflowRequestSummaryOut[];
  next_cursor: string | null;
};

export type WorkflowRequestStepOut = {
  id: UUID;
  step_order: number;
  assignee_type: string | null;
  assignee_role_code: string | null;
  assignee_user_id: UUID | null;
  assignee_user_ids: UUID[];
  decision: string | null;
  decided_at: string | null;
  decided_by_user_id: UUID | null;
  comment: string | null;
  created_at: string;
};

export type WorkflowRequestCommentOut = {
  id: UUID;
  author_user_id: UUID;
  body: string;
  created_at: string;
};

export type WorkflowRequestAttachmentOut = {
  id: UUID;
  file_id: UUID;
  uploaded_by_user_id: UUID | null;
  note: string | null;
  created_at: string;
};

export type WorkflowRequestEventOut = {
  id: UUID;
  actor_user_id: UUID | null;
  event_type: string;
  data: Record<string, unknown>;
  correlation_id: string | null;
  created_at: string;
};

export type WorkflowRequestDetailOut = {
  request: WorkflowRequestSummaryOut;
  steps: WorkflowRequestStepOut[];
  comments: WorkflowRequestCommentOut[];
  attachments: WorkflowRequestAttachmentOut[];
  events: WorkflowRequestEventOut[];
};

// Approve/reject/cancel return a small action payload (not the full request).
export type WorkflowRequestActionOut = {
  id: string;
  status: string;
  current_step?: number;
  cancelled_at?: string;
};

export type WorkflowDefinitionCreateIn = {
  request_type_code: string;
  code: string;
  name: string;
  version: number;
  company_id?: UUID | null;
};

export type WorkflowDefinitionStepIn = {
  step_index: number;
  assignee_type: "MANAGER" | "ROLE" | "USER" | string;
  assignee_role_code?: string | null;
  assignee_user_id?: UUID | null;
  scope_mode?: "TENANT" | "COMPANY" | "BRANCH" | string;
  fallback_role_code?: string | null;
};

export type WorkflowDefinitionStepsIn = {
  steps: WorkflowDefinitionStepIn[];
};

export type WorkflowDefinitionStepOut = {
  step_index: number;
  assignee_type: string;
  assignee_role_code: string | null;
  assignee_user_id: UUID | null;
  scope_mode: string;
  fallback_role_code: string | null;
};

export type WorkflowDefinitionOut = {
  id: UUID;
  tenant_id: UUID;
  company_id: UUID | null;
  request_type_code: string;
  code: string | null;
  name: string;
  version: number | null;
  is_active: boolean;
  created_by_user_id: UUID | null;
  created_at: string;
  updated_at: string;
  steps: WorkflowDefinitionStepOut[];
};

// ----- DMS (files, used by workflow attachments) -----
export type DmsFileOut = {
  id: UUID;
  tenant_id: UUID;
  storage_provider: "LOCAL" | "S3" | string;
  original_filename: string;
  content_type: string;
  size_bytes: number;
  sha256: string | null;
  status: "UPLOADING" | "READY" | "FAILED" | "DELETED" | string;
  created_by_user_id: UUID | null;
  created_at: string;
  updated_at: string;
  meta: Record<string, unknown> | null;
};

export type DmsDocumentTypeCreateIn = {
  code: string;
  name: string;
  requires_expiry?: boolean;
  is_active?: boolean;
};

export type DmsDocumentTypePatchIn = {
  name?: string | null;
  requires_expiry?: boolean | null;
  is_active?: boolean | null;
};

export type DmsDocumentTypeOut = {
  id: UUID;
  tenant_id: UUID;
  code: string;
  name: string;
  requires_expiry: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type DmsDocumentTypesOut = {
  items: DmsDocumentTypeOut[];
};

export type DmsDocumentVersionOut = {
  id: UUID;
  tenant_id: UUID;
  document_id: UUID;
  file_id: UUID;
  version: number;
  notes: string | null;
  created_by_user_id: UUID | null;
  created_at: string;
};

export type DmsEmployeeDocumentCreateIn = {
  document_type_code: string;
  file_id: UUID;
  expires_at?: string | null;
  notes?: string | null;
};

export type DmsDocumentAddVersionIn = {
  file_id: UUID;
  notes?: string | null;
};

export type DmsDocumentOut = {
  id: UUID;
  tenant_id: UUID;
  document_type_id: UUID;
  document_type_code: string;
  document_type_name: string;
  owner_employee_id: UUID | null;
  status: "DRAFT" | "SUBMITTED" | "VERIFIED" | "REJECTED" | "EXPIRED" | string;
  expires_at: string | null;
  current_version_id: UUID | null;
  current_version: DmsDocumentVersionOut | null;
  verified_at: string | null;
  verified_by_user_id: UUID | null;
  rejected_reason: string | null;
  created_by_user_id: UUID | null;
  verification_workflow_request_id: UUID | null;
  created_at: string;
  updated_at: string;
  meta: Record<string, unknown> | null;
};

export type DmsDocumentListOut = {
  items: DmsDocumentOut[];
  next_cursor: string | null;
};

export type DmsVerifyRequestOut = {
  workflow_request_id: UUID;
};

export type DmsExpiryRuleCreateIn = {
  document_type_code: string;
  days_before: number;
  is_active?: boolean;
};

export type DmsExpiryRuleOut = {
  id: UUID;
  tenant_id: UUID;
  document_type_id: UUID | null;
  document_type_code: string | null;
  document_type_name: string | null;
  days_before: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
};

export type DmsExpiryRulesOut = {
  items: DmsExpiryRuleOut[];
};

export type DmsUpcomingExpiryItemOut = {
  document_id: UUID;
  document_type_code: string;
  document_type_name: string;
  owner_employee_id: UUID | null;
  expires_at: string;
  days_left: number;
  status: "DRAFT" | "SUBMITTED" | "VERIFIED" | "REJECTED" | "EXPIRED" | string;
};

export type DmsUpcomingExpiryOut = {
  items: DmsUpcomingExpiryItemOut[];
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
