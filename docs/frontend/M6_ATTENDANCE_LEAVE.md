# M6 — Attendance + Leave Daily-Use Pack (Frontend)

Milestone 6 ships the first “daily-use” ESS/MSS pack in the Noor HRMS web app (`frontend/`):

- ESS Attendance: Punch, Days, Corrections (submit + list + cancel)
- ESS Leave: Balances + Requests + Apply leave + Cancel
- MSS Leave: Team Calendar (approved spans)
- Workflow integration: domain requests create workflow requests; approvals happen via Workflow Inbox (M5)

Non-goals:
- No new backend endpoints/features
- No bespoke UI outside DS v0 templates/components
- No approval UI inside attendance/leave screens (we reuse Workflow module)

## Navigation

Routes under `/attendance/*` and `/leave/*` are owned by **Self Service** (ESS) in the top bar.
Team calendar is a manager view and is highlighted under **My Team** (MSS).

Implementation: `frontend/src/config/navigation.ts`

ESS sidebar:
- `/attendance/punch`
- `/attendance/days`
- `/attendance/corrections`
- `/leave`
- `/ess/me`

MSS sidebar:
- `/mss/team`
- `/leave/team-calendar`

## Routes

Attendance (ESS):
- `/attendance/punch`
- `/attendance/days`
- `/attendance/corrections`
- `/attendance/corrections/new`

Leave (ESS/MSS):
- `/leave`
- `/leave/team-calendar`

## Permissions (frontend gating)

Attendance:
- Punch read: `attendance:punch:read`
- Punch submit: `attendance:punch:submit`
- Days/corrections read: `attendance:correction:read`
- Submit/cancel corrections: `attendance:correction:submit`

Leave (ESS):
- Read balances: `leave:balance:read`
- Read requests: `leave:request:read`
- Submit/cancel requests: `leave:request:submit`

Leave (MSS):
- Team calendar: `leave:team:read`

DMS (attachments):
- Upload evidence/attachments: `dms:file:read` + `dms:file:write`

Note: permission gating is UX-only; backend remains authoritative.

## Backend Endpoints Used

Attendance (ESS):
- `GET  /api/v1/attendance/me/punch-state`
- `POST /api/v1/attendance/me/punch-in`
- `POST /api/v1/attendance/me/punch-out`
- `GET  /api/v1/attendance/me/days?from=YYYY-MM-DD&to=YYYY-MM-DD`
- `POST /api/v1/attendance/me/corrections`
- `GET  /api/v1/attendance/me/corrections?status&limit&cursor`
- `POST /api/v1/attendance/me/corrections/{correction_id}/cancel`

Leave (ESS):
- `GET  /api/v1/leave/me/balances?year=`
- `GET  /api/v1/leave/me/requests?status&limit&cursor`
- `POST /api/v1/leave/me/requests`
- `POST /api/v1/leave/me/requests/{leave_request_id}/cancel`

Leave (MSS):
- `GET /api/v1/leave/team/calendar?from&to&depth=1|all&branch_id?`

Workflow integration (M5):
- We link to `/workflow/requests/{workflow_request_id}` from correction/leave results.
- Managers approve/reject in `/workflow/inbox`.

DMS (evidence uploads):
- `POST /api/v1/dms/files` (multipart upload)

## Frontend Architecture

Feature modules:
- Attendance:
  - `frontend/src/features/attendance/api/attendance.ts`
  - `frontend/src/features/attendance/queryKeys.ts`
  - `frontend/src/features/attendance/correctionMapping.ts`
- Leave:
  - `frontend/src/features/leave/api/leave.ts`
  - `frontend/src/features/leave/queryKeys.ts`

Shared utilities:
- Local-time safe date helpers:
  - `frontend/src/lib/dateRange.ts`

Error UX (M2 hardening):
- Friendly mapping for M6 error codes in `frontend/src/lib/errorUx.ts`
- All network calls go through `frontend/src/lib/api.ts` (ApiError normalization + correlation ids)

## UX Details / Determinism

Attendance Punch:
- Loads punch state and shows a single primary action (Punch in/out).
- Mutations use client-side idempotency keys and refetch state on success.

Attendance Days:
- Month range only (Prev/Next month).
- List + right detail panel (T1 template).
- “Request correction” deep links to `/attendance/corrections/new?day=YYYY-MM-DD`.

Corrections:
- Submit form derives `requested_override_status` from `correction_type` (v1 default mapping).
- Evidence upload is optional and permission-gated.
- List uses cursor pagination with “Load more”.
- Cancel is available only for `PENDING` corrections.

Leave:
- Balances render in the right panel; requests list uses cursor pagination.
- Apply leave is disabled unless company+branch scope is selected (StorePicker guidance).
- Attachments are optional and permission-gated.
- Cancel is available only for `PENDING` requests.

Team Calendar:
- Month grid with leave-type count chips per day.
- Depth toggle triggers a new request.
- Only approved spans are expected (backend contract).

## Testing

Unit + component tests:
- `cd frontend && npm run test`

Key M6 component tests:
- Punch: `frontend/src/app/attendance/punch/__tests__/page.test.tsx`
- Days: `frontend/src/app/attendance/days/__tests__/page.test.tsx`
- Submit correction: `frontend/src/app/attendance/corrections/new/__tests__/page.test.tsx`
- Corrections list/cancel: `frontend/src/app/attendance/corrections/__tests__/page.test.tsx`
- Leave apply: `frontend/src/app/leave/__tests__/page.test.tsx`
- Team calendar: `frontend/src/app/leave/team-calendar/__tests__/page.test.tsx`

Story-level (workflow-integrated) tests:
- `frontend/src/app/__tests__/m6.stories.test.tsx`
  - attendance correction submit -> workflow approve -> days reflect override
  - leave apply -> workflow approve -> balances/requests/calendar reflect approval

MSW handlers:
- `frontend/src/test/msw/handlers/attendance.handlers.ts`
- `frontend/src/test/msw/handlers/leave.handlers.ts`

