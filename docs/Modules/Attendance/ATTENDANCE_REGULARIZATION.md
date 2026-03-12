# Attendance Regularization v1 (Milestone 4)

This repo includes an enterprise-safe **Attendance Regularization** feature that allows employees to submit
attendance corrections for a specific day, with approvals powered by **Workflow Engine v1**.

Design principle:
- Attendance regularization stores canonical business facts in `attendance.attendance_corrections`.
- Workflow stores approvals/steps/decisions + in-app notifications.
- On terminal approval, a deterministic override is written to `attendance.day_overrides`.

Linking:
- `workflow.requests.entity_type = "attendance.attendance_correction"`
- `workflow.requests.entity_id   = attendance.attendance_corrections.id`

## Conventions (applies to all endpoints)

- Base path: `/api/v1` only
- Stable JSON envelope:
  - Success: `{ "ok": true, "data": ... }`
  - Error: `{ "ok": false, "error": { "code": "...", "message": "...", "details"?: ..., "correlation_id"?: "..." } }`
- Correlation id is returned in `X-Correlation-Id` and echoed in error payloads.
- Tenant isolation is **fail-closed**:
  - Multi-tenant users must send `X-Tenant-Id` (else `400 TENANT_REQUIRED`).
  - All queries are tenant-scoped in SQL.
- RBAC uses colon-style permissions (cached in Redis) enforced via `require_permission(...)`.

## Database

Schema: `attendance`

### `attendance.attendance_corrections`
Canonical correction request record (queryable/reportable without workflow JSON):
- `id uuid` (PK)
- `tenant_id uuid` (FK tenancy.tenants)
- `employee_id uuid` (FK hr_core.employees)
- `branch_id uuid` (FK tenancy.branches) (captured from current employment at submit time)
- `day date`
- `correction_type` (`MISSED_PUNCH` / `MARK_PRESENT` / `MARK_ABSENT` / `WFH` / `ON_DUTY`)
- `requested_override_status` (`PRESENT_OVERRIDE` / `ABSENT_OVERRIDE` / `WFH` / `ON_DUTY`)
- `reason text` (optional; may be required via config)
- `evidence_file_ids uuid[]` (optional; validated against `dms.files`)
- `status` (`PENDING` / `APPROVED` / `REJECTED` / `CANCELED`)
- `workflow_request_id uuid` (nullable FK workflow.requests; set on submit)
- `idempotency_key text` (optional)
- `created_at timestamptz`, `updated_at timestamptz`

Hardening:
- Partial unique `(tenant_id, employee_id, idempotency_key)` where idempotency_key is not null
- Partial unique `(tenant_id, employee_id, day)` where status='PENDING' (prevents multiple pending for the same day)

### `attendance.day_overrides`
Runtime truth-layer for effective day status.

Milestone 4 extends the existing Leave integration (`ON_LEAVE`) to support correction overrides:
- `override_kind` (`LEAVE` | `CORRECTION`)
- `notes` (optional)
- `payload` (optional JSONB, e.g. `{ "correction_type": "MISSED_PUNCH" }`)

Allowed statuses in v1:
- `ON_LEAVE` (Leave v1)
- `PRESENT_OVERRIDE`
- `ABSENT_OVERRIDE`
- `WFH`
- `ON_DUTY`

Allowed source_type in v1:
- `LEAVE_REQUEST`
- `ATTENDANCE_CORRECTION`

Idempotency:
- Unique `(tenant_id, employee_id, day, source_type, source_id)` ensures the workflow hook can safely retry.

### Base attendance source (`attendance.attendance_daily`)

For v1, the ESS "days" endpoint treats base attendance as:
- a row exists in `attendance.attendance_daily` for `(tenant_id, employee_id, business_date)` => base `PRESENT`
- otherwise => base `ABSENT`

The correction feature does **not** modify raw punches/events. It layers deterministic overrides via
`attendance.day_overrides`.

## Override precedence (deterministic)

Effective status precedence for a day:
1) `ON_LEAVE` override wins over everything.
2) Correction override wins over base attendance.
3) Otherwise, base attendance determines status.

Leave conflict rule (v1):
- A correction request cannot be created/approved for a day that is on leave (`ON_LEAVE` override exists).

## Workflow integration

Request type code:
- `ATTENDANCE_CORRECTION` (seeded via Alembic)

To submit attendance corrections, the tenant/company must have an **active** workflow definition for
`ATTENDANCE_CORRECTION` (commonly a single step `MANAGER`).

Terminal hooks:
- On workflow `approved`: write `attendance.day_overrides` with `override_kind='CORRECTION'` and set
  `attendance.attendance_corrections.status='APPROVED'` (idempotent).
- On workflow `rejected`: set correction status to `REJECTED`.
- On workflow `cancelled`: set correction status to `CANCELED`.

All side-effects run inside the workflow transaction (no separate commits).

Evidence attachments:
- When `evidence_file_ids` are provided on submit, the service inserts rows into:
  - `workflow.request_attachments (tenant_id, request_id, file_id, created_by, note)`
- This allows approvers to view evidence via the workflow request detail endpoints.

## Permissions (colon-style)

Seeded via Alembic and mapped to default roles:
- `attendance:correction:submit`
- `attendance:correction:read`
- `attendance:team:read`
- `attendance:admin:read`

Approvals continue to use workflow permissions (e.g. `workflow:request:approve`).

## Config (env vars)

Defined in `backend/app/core/config.py`:
- `ATTENDANCE_CORRECTION_MAX_DAYS_BACK` (default: 45)
- `ATTENDANCE_CORRECTION_ALLOW_FUTURE_DAYS` (default: false)
- `ATTENDANCE_CORRECTION_REQUIRE_REASON` (default: true)

## Business rules (v1)

### Submit-time validation

On `POST /attendance/me/corrections`:
- Day window:
  - too old => `400 attendance.correction.too_old`
  - future day (when disallowed) => `400 attendance.correction.future_not_allowed`
- Reason:
  - required but missing/blank => `400 attendance.correction.reason_required`
- Leave conflict:
  - if an `ON_LEAVE` override exists => `409 attendance.correction.conflict.leave`
- Pending uniqueness:
  - if a `PENDING` correction exists for the same day => `409 attendance.correction.pending_exists`
- Idempotency:
  - same `(tenant_id, employee_id, idempotency_key)` and same payload => returns the existing record
  - same key but different payload => `409 attendance.correction.idempotency.conflict`
- Evidence files (optional):
  - if `evidence_file_ids` provided, caller must have `dms:file:read` and all file_ids must exist in `dms.files`

### Approval-time validation (race-safe)

On workflow approval, the hook re-checks leave conflict to prevent a race:
- if leave override appears after submit but before approval => approval fails with
  `409 attendance.correction.conflict.leave`

## Audit

The module records audit rows (minimal payload; no sensitive values):
- `attendance.correction.create`
- `attendance.correction.approved`
- `attendance.correction.rejected`
- `attendance.correction.cancel`

## API (all under `/api/v1`)

ESS (Employee Self Service):
- `GET  /attendance/me/days?from=YYYY-MM-DD&to=YYYY-MM-DD`
  - Permission: `attendance:correction:read`
  - Returns day-by-day effective status.
  - Override selection rules:
    - if any `ON_LEAVE` exists for the day => effective `ON_LEAVE`
    - else newest correction override for the day (by `created_at DESC`) => effective override status
    - else base status

Example response item:
```json
{
  "day": "2026-02-15",
  "base_status": "PRESENT",
  "effective_status": "WFH",
  "override": {
    "kind": "CORRECTION",
    "status": "WFH",
    "source_type": "ATTENDANCE_CORRECTION",
    "source_id": "00000000-0000-0000-0000-000000000000"
  }
}
```

- `POST /attendance/me/corrections`
  - Permission: `attendance:correction:submit`
  - Body:
```json
{
  "day": "2026-02-15",
  "correction_type": "MISSED_PUNCH",
  "requested_override_status": "PRESENT_OVERRIDE",
  "reason": "Missed punch-in due to device issue",
  "evidence_file_ids": [],
  "idempotency_key": "my-client-key-123"
}
```

- `GET  /attendance/me/corrections?status=&limit=&cursor=`
  - Permission: `attendance:correction:read`
  - Cursor pagination: `"created_at_iso|uuid"`

- `POST /attendance/me/corrections/{correction_id}/cancel`
  - Permission: `attendance:correction:submit`
  - Participant-only: only the requester can cancel; otherwise `404 attendance.correction.not_found`
  - Only `PENDING` can be cancelled; else `409 attendance.correction.not_pending`

Admin (tenant-scoped listing):
- `GET /attendance/corrections?status=&branch_id=&from=&to=&limit=&cursor=`
  - Permission: `attendance:admin:read`
  - Tenant-scoped list of correction requests (reporting surface)

Approvals are performed via workflow engine:
- `GET  /workflow/inbox`
- `POST /workflow/requests/{request_id}/approve`
- `POST /workflow/requests/{request_id}/reject`

## Error codes (v1)

HTTP `400`:
- `attendance.correction.too_old`
- `attendance.correction.future_not_allowed`
- `attendance.correction.reason_required`

HTTP `404` (participant-only semantics):
- `attendance.correction.not_found`

HTTP `409`:
- `attendance.correction.not_pending`
- `attendance.correction.conflict.leave`
- `attendance.correction.pending_exists`
- `attendance.correction.idempotency.conflict`

## Notes on attendance summaries

The existing branch daily summary endpoint:
- `GET /api/v1/branches/{branch_id}/attendance/daily`

now accounts for overrides:
- `ON_LEAVE` excludes employees from the present count.
- Correction overrides can mark employees present/absent even if base rows disagree.

Presence mapping in v1 summary logic:
- `PRESENT_OVERRIDE`, `WFH`, `ON_DUTY` => treated as "present"
- `ABSENT_OVERRIDE` => treated as "absent"
- Late/average calculations use the base `attendance.attendance_daily` row only (if effectively present).

---

# CCTV / Vision Pipeline (Base Attendance)

Attendance Regularization (corrections + overrides) sits on top of a **base attendance**
data source that is produced by the CCTV/Vision pipeline.

High-level:
- **Vision** ingests CCTV door videos, detects/tracks people, and attempts face recognition.
- The pipeline emits **entry/exit events** and rollups them into **daily punch-in/out**
  rows in `attendance.attendance_daily`.
- Attendance Regularization then layers deterministic overrides (`attendance.day_overrides`)
  without mutating raw events.

Important note about conventions:
- These Vision/Face endpoints are under `/api/v1`, but **they are legacy-style and not
  wrapped in the `{ok:true,data}` envelope** (they return `response_model` objects and
  use `HTTPException` errors).
- Tenant isolation + RBAC still apply through `AuthContext` + `require_permission(...)`.

## Database schemas (Vision + Attendance)

### `vision.cameras`
Camera registry per branch:
- `tenant_id`, `branch_id`
- `name`, `placement`
- `calibration_json jsonb` (raw calibration configuration consumed by the worker)
- `created_at`

### `vision.videos`
Uploaded CCTV footage metadata:
- `tenant_id`, `branch_id`, `camera_id`
- `business_date`
- `file_path` (relative to `settings.data_dir`)
- `sha256` (filled on finalize)
- optional metadata: `duration_sec`, `fps`, `width`, `height`, `recorded_start_ts`
- `uploaded_by`, `uploaded_at`

### `vision.jobs`
One processing run per uploaded video:
- `video_id`
- `status` (`PENDING|RUNNING|POSTPROCESSING|DONE|FAILED|CANCELED`)
- `progress` (0..100-ish)
- `pipeline_version`
- `model_versions_json`, `config_json` (for reproducibility/debug)
- `error`, `created_at`, `started_at`, `finished_at`

### `vision.tracks`
Tracked person “tracklets” inside a job:
- unique `(job_id, track_key)`
- `first_ts`, `last_ts`
- optional `employee_id` + `identity_confidence` (if recognition succeeds)
- `best_snapshot_path` (used by recompute/identity backfills)
- `assigned_type` (`employee|visitor|unknown`)

### `vision.events`
Door events emitted by the event engine:
- `job_id`, `ts`
- `event_type` (`entry|exit`)
- `track_key`, optional `entrance_id`
- optional `employee_id` + `confidence`
- optional `snapshot_path`
- `is_inferred` (debounce/inference)
- `meta jsonb`

### `attendance.attendance_daily`
Base attendance rollup used by reporting and by Attendance Regularization “base layer”:
- unique `(branch_id, business_date, employee_id)`
- `punch_in`, `punch_out`, `total_minutes`, optional `confidence`
- `anomalies_json` (e.g. absent flags / gaps)

### `vision.metrics_hourly` and `vision.artifacts`
Optional reporting helpers:
- `vision.metrics_hourly`: entries/exits/visitors/dwell per hour per job
- `vision.artifacts`: generated exports per job (CSV/JSON), stored as relative paths
  under `settings.data_dir`

## Camera calibration JSON (door logic)

The worker reads `vision.cameras.calibration_json` and parses it into a `ZoneConfig`
(see `backend/app/worker/zones.py`).

Supported keys (recommended; includes backward-compatible aliases):
- Coordinate space:
  - `coord_space`: `"pixel"` (default) or `"normalized"`
  - `frame_width`, `frame_height` OR `frame_size: {w,h}` (reference size for scaling)
- Polygons:
  - `door_roi_polygon`: `[[x,y], ...]`
  - `inside_zone_polygon`: `[[x,y], ...]`
  - `outside_zone_polygon`: `[[x,y], ...]`
  - `ignore_mask_polygons`: `[ [[x,y],...], ... ]`
- Door line (optional):
  - `entry_line`: `[[x,y],[x,y]]` OR `{p1:[x,y], p2:[x,y]}`
  - `inside_test_point`: `[x,y]`
  - `neutral_band_px` (or `neutral_band_norm` when `coord_space=normalized`)

The event engine uses a point-based approach (typically bbox “foot point”) and
debounces zone transitions to emit entry/exit events.

## Face recognition (training library)

The repo includes a Frigate-style “face library” used by the runtime recognizer:
- Training images are stored on disk:
  - `<FACE_DIR>/<tenant_id>/<branch_id>/<employee_id>/*.jpg`
- Prototypes are built in memory per branch and used to assign `employee_id` to tracks.

There is also a `face.employee_faces` pgvector table in the baseline schema, but the
current runtime recognizer uses the file-based library for prototypes.

## Permissions (Vision/Face)

Vision:
- `vision:camera:read`, `vision:camera:write`
- `vision:video:upload`
- `vision:job:run`
- `vision:results:read`

Face:
- `face:library:read`, `face:library:write`
- `face:recognize`

## APIs (Vision/Face)

All routes are under `/api/v1` (legacy style: not enveloped).

### Cameras
- `POST /api/v1/branches/{branch_id}/cameras`
  - Permission: `vision:camera:write`
  - Creates a camera row (including optional `calibration_json`).
- `GET /api/v1/branches/{branch_id}/cameras`
  - Permission: `vision:camera:read`
- `GET /api/v1/branches/{branch_id}/cameras/{camera_id}`
  - Permission: `vision:camera:read`
- `PUT /api/v1/branches/{branch_id}/cameras/{camera_id}/calibration`
  - Permission: `vision:camera:write`
- `POST /api/v1/branches/{branch_id}/cameras/{camera_id}/calibration/validate?video_id=...`
  - Permission: `vision:camera:read`
  - Validates `calibration_json` and can optionally scale against a specific video’s `width/height`.

### Videos (CCTV ingestion)
- `POST /api/v1/branches/{branch_id}/videos/init`
  - Permission: `vision:video:upload`
  - Creates `vision.videos` row and returns upload/finalize endpoints.
- `PUT /api/v1/branches/{branch_id}/videos/{video_id}/file`
  - Permission: `vision:video:upload`
  - Uploads video bytes to `<data_dir>/<video.file_path>` using `*.part` atomic rename.
- `POST /api/v1/branches/{branch_id}/videos/{video_id}/finalize`
  - Permission: `vision:video:upload`
  - Computes sha256 and (best-effort) fills fps/duration/width/height via ffprobe.

### Jobs (processing runs)
- `POST /api/v1/branches/{branch_id}/videos/{video_id}/jobs`
  - Permission: `vision:job:run`
  - Creates `vision.jobs` and enqueues the worker to process the video.
- `GET /api/v1/branches/{branch_id}/jobs/{job_id}`
  - Permission: `vision:results:read`
  - Polling endpoint for UI.
- `POST /api/v1/branches/{branch_id}/jobs/{job_id}/cancel`
  - Permission: `vision:job:run`
- `POST /api/v1/branches/{branch_id}/jobs/{job_id}/retry`
  - Permission: `vision:job:run`
- `POST /api/v1/branches/{branch_id}/jobs/{job_id}/recompute`
  - Permission: `vision:job:run`
  - Re-assign identities for existing tracks (using face library) and optionally recompute rollups/artifacts.

### Results (events + rollups + artifacts)
- `GET /api/v1/branches/{branch_id}/jobs/{job_id}/events?event_type=&employee_id=&is_inferred=&limit=&offset=`
  - Permission: `vision:results:read`
- `GET /api/v1/branches/{branch_id}/events/{event_id}/snapshot`
  - Permission: `vision:results:read`
  - Downloads a per-event snapshot image (path-safe).
- `GET /api/v1/branches/{branch_id}/jobs/{job_id}/attendance`
  - Permission: `vision:results:read`
  - Job-scoped attendance rollup.
- `GET /api/v1/branches/{branch_id}/attendance/daily?start=YYYY-MM-DD&end=YYYY-MM-DD`
  - Permission: `vision:results:read`
  - Branch/day summary (this endpoint is also override-aware; see above).
- `GET /api/v1/branches/{branch_id}/jobs/{job_id}/metrics/hourly`
  - Permission: `vision:results:read`
- `GET /api/v1/branches/{branch_id}/jobs/{job_id}/artifacts`
  - Permission: `vision:results:read`
- `GET /api/v1/branches/{branch_id}/artifacts/{artifact_id}/download`
  - Permission: `vision:results:read`
  - Downloads export files generated after job completion.

### Face library (training + recognition)
- `GET /api/v1/branches/{branch_id}/faces`
  - Permission: `face:library:read`
- `POST /api/v1/branches/{branch_id}/employees/{employee_id}/faces/register` (multipart file)
  - Permission: `face:library:write`
  - Detects and crops the best face and stores it into the file-based face library.
- `DELETE /api/v1/branches/{branch_id}/employees/{employee_id}/faces/{filename}`
  - Permission: `face:library:write`
- `POST /api/v1/branches/{branch_id}/faces/recognize` (multipart file)
  - Permission: `face:recognize`
  - Returns top-k matches + confidence.
- `POST /api/v1/branches/{branch_id}/faces/clear`
  - Permission: `face:library:write`
- `POST /api/v1/branches/{branch_id}/faces/rebuild`
  - Permission: `face:library:write`

## How this links to Attendance Regularization

The relationship is intentionally layered:
1) Vision pipeline produces base attendance (`attendance.attendance_daily`) from CCTV videos.
2) Leave v1 writes `attendance.day_overrides` (`override_kind=LEAVE`, `status=ON_LEAVE`).
3) Attendance Regularization writes `attendance.day_overrides` (`override_kind=CORRECTION`, `status=...`).
4) Read paths (ESS `/attendance/me/days` and branch summaries) apply deterministic precedence:
   `ON_LEAVE` > correction override > base attendance.
