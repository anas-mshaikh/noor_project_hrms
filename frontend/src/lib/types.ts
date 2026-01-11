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
  is_active: boolean;
  created_at: string;
};

export type FaceCreatedOut = {
  face_id: UUID;
  employee_id: UUID;
  snapshot_path: string;
  model_version: string;
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
