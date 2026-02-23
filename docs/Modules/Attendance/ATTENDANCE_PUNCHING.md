# Attendance Punching v1 (Milestone 7)

This document describes the Attendance Punching v1 system:
- Zoho-style punch in/out toggle for ESS users
- Payroll-ready worked minutes (branch timezone business day)
- Override-aware attendance reads for both **status** and **minutes**
- A safety worker that auto-closes abandoned sessions

Important: **CCTV/Vision is not integrated into punching v1**. The data model is
future-proofed with a `source` field so biometric/CCTV/import pipelines can
insert punches later without schema churn.

---

## Core Concepts

### Business Day (Branch Timezone)
"Today" and daily payroll minutes are computed using the **branch timezone**
(`tenancy.branches.timezone`), not UTC.

Why:
- A punch at 23:30 UTC may belong to the next day for a UTC+3 branch.
- Payroll, summaries, and "today" UI must match local operations.

### Precedence (Status + Minutes)
Effective day status and minutes use the existing precedence model:

1) `ON_LEAVE` override wins over everything  
2) `CORRECTION` overrides win over base attendance  
3) Otherwise base attendance (derived from `attendance.attendance_daily`)

For minutes:
- `ON_LEAVE` => `0`
- Else if correction override has `payload.override_minutes` => that value
- Else if correction status is `ABSENT_OVERRIDE` => `0`
- Else => base minutes (`attendance_daily.total_minutes`, default `0`)

---

## Data Model (Postgres)

### `attendance.punch_settings` (branch configuration)
Branch-level punching configuration (lazily created with defaults).

Columns:
- `tenant_id uuid` (PK part, FK `tenancy.tenants`)
- `branch_id uuid` (PK part, FK `tenancy.branches`)
- `is_enabled bool` (default `true`)
- `allow_multiple_sessions_per_day bool` (default `true`)
- `max_session_hours int` (default `16`)
- `require_location bool` (default `false`, placeholder)
- `geo_fence_json jsonb null` (placeholder)
- `created_at`, `updated_at` (+ `public.set_updated_at()` trigger)

### `attendance.punches` (immutable events)
Append-only punch events.

Columns:
- `id uuid` (PK)
- `tenant_id`, `branch_id`, `employee_id`
- `ts timestamptz` (stored in UTC)
- `action text` CHECK `IN|OUT`
- `source text` CHECK:
  - `MANUAL_WEB`, `MANUAL_MOBILE`, `SYSTEM`, `BIOMETRIC`, `CCTV`, `IMPORT`
- `source_ref_type text null`, `source_ref_id uuid null` (future)
- `created_by_user_id uuid null` (system punches may be null)
- `idempotency_key text null` (partial unique per employee)
- `meta jsonb null`
- `created_at`

### `attendance.work_sessions` (paired sessions)
Represents one open/closed work session. Exactly **one OPEN** session is allowed
per employee (enforced via partial unique index).

Columns:
- `id uuid` (PK)
- `tenant_id`, `branch_id`, `employee_id`
- `business_date date` (derived from branch timezone using **start_ts**)
- `start_ts timestamptz`
- `end_ts timestamptz null`
- `minutes int` (floor minutes, clamped)
- `start_punch_id uuid`, `end_punch_id uuid null`
- `status text` CHECK `OPEN|CLOSED|AUTO_CLOSED`
- `source_start text`, `source_end text null`
- `anomaly_code text null` (`MISSING_OUT`, `SESSION_TOO_LONG`, `CROSSED_MIDNIGHT` in v1)
- `created_at`, `updated_at` (+ trigger)

### `attendance.attendance_daily` (derived rollup)
Punching v1 extends `attendance.attendance_daily` with:
- `source_breakdown jsonb null` (e.g. `{"MANUAL_WEB": 420}`)
- `has_open_session bool not null default false`

This table is still compatible with the legacy vision rollup pipeline.

### `attendance.day_overrides` payload conventions
Punching v1 does not require new columns in `day_overrides`. v1 uses the existing
`payload jsonb` for optional minute overrides:

```json
{
  "override_minutes": 123
}
```

---

## API (v1, `/api/v1` only, enveloped JSON)

### ESS

#### `POST /api/v1/attendance/me/punch-in`
Permission: `attendance:punch:submit`

Body:
```json
{
  "idempotency_key": "string?",
  "meta": { "any": "json" }?
}
```

Behavior:
- Derives branch from current employment (`hr_core.v_employee_current_employment`).
- Rejects punch-in if:
  - branch punching disabled => `409 attendance.punch.disabled`
  - day has `ON_LEAVE` override => `409 attendance.punch.conflict.leave`
  - open session exists => `409 attendance.punch.already_in`
- Creates:
  - `attendance.punches` row (`action=IN`, `source=MANUAL_WEB`)
  - `attendance.work_sessions` OPEN row
  - upserts `attendance.attendance_daily` with `has_open_session=true`

#### `POST /api/v1/attendance/me/punch-out`
Permission: `attendance:punch:submit`

Behavior:
- Locks the OPEN session row and closes it.
- Clamps end_ts to:
  - max session length (`max_session_hours`)
  - local midnight boundary after the session business_date
- Recomputes daily minutes from closed sessions.
- Errors:
  - no OPEN session => `409 attendance.punch.not_in`

#### `GET /api/v1/attendance/me/punch-state`
Permission: `attendance:punch:read`

Response:
```json
{
  "today_business_date": "YYYY-MM-DD",
  "is_punched_in": true,
  "open_session_started_at": "timestamptz|null",
  "base_minutes_today": 0,
  "effective_minutes_today": 0,
  "effective_status_today": "PRESENT|ABSENT|ON_LEAVE|PRESENT_OVERRIDE|ABSENT_OVERRIDE|WFH|ON_DUTY"
}
```

#### `GET /api/v1/attendance/me/days?from=YYYY-MM-DD&to=YYYY-MM-DD`
Existing endpoint extended in Milestone 7 to include:
- `base_minutes`, `effective_minutes`
- `first_in`, `last_out`
- `has_open_session`
- `sources` (from `source_breakdown` keys)

This endpoint remains override-aware with precedence `LEAVE > CORRECTION > BASE`.

### Admin

#### `GET /api/v1/attendance/punch-settings?branch_id=<uuid>`
Permission: `attendance:settings:write`

Notes:
- Lazily creates defaults if missing.
- Enforces `branch_id` matches active scope (`X-Branch-Id`) to avoid cross-branch access.

#### `PUT /api/v1/attendance/punch-settings?branch_id=<uuid>`
Permission: `attendance:settings:write`

Body (partial):
```json
{
  "is_enabled": true,
  "allow_multiple_sessions_per_day": true,
  "max_session_hours": 16
}
```

---

## Worker: Auto-close OPEN sessions

Module:
- `backend/app/worker/attendance_session_worker.py`

Function:
- `run_once(now_ts=..., limit=...) -> int`

Behavior:
- Finds OPEN sessions and auto-closes when:
  - `now - start_ts > max_session_hours`, or
  - the branch-local business date moved beyond session.business_date
- Updates session:
  - `status=AUTO_CLOSED`, `anomaly_code=MISSING_OUT`, `source_end=SYSTEM`
- Recomputes daily rollup.
- Inserts:
  - audit row `attendance.session.auto_closed`
  - notification outbox rows `attendance.session.auto_closed` (dedupe per session+user)

---

## Legacy CCTV/Vision Attendance (Important)

This repo already includes CCTV/Vision processing that can populate
`attendance.attendance_daily` based on camera events.

Milestone 7:
- does **not** remove or break that pipeline
- does **not** wire it into punching v1
- does make punching future-proof so that a later milestone can insert punches
  using `source=CCTV` or `source=BIOMETRIC` with stable references.

