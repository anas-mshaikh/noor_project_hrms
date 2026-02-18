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

## Database

Schema: `attendance`

### `attendance.attendance_corrections`
Canonical correction request record (queryable/reportable without workflow JSON):
- `day` (date)
- `correction_type` (MISSED_PUNCH / MARK_PRESENT / MARK_ABSENT / WFH / ON_DUTY)
- `requested_override_status` (PRESENT_OVERRIDE / ABSENT_OVERRIDE / WFH / ON_DUTY)
- `reason` (optional; may be required via config)
- `evidence_file_ids` (`uuid[]`, optional)
- `status` (PENDING / APPROVED / REJECTED / CANCELED)
- `workflow_request_id` link to `workflow.requests` (nullable; set on submit)
- `idempotency_key` (optional)

Hardening:
- Partial unique `(tenant_id, employee_id, idempotency_key)` where idempotency_key is not null
- Partial unique `(tenant_id, employee_id, day)` where status='PENDING' (prevents multiple pending for the same day)

### `attendance.day_overrides`
Runtime truth-layer for effective day status.

Milestone 4 extends the existing Leave integration (`ON_LEAVE`) to support correction overrides:
- `override_kind` (LEAVE | CORRECTION)
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

## API (all under `/api/v1`, enveloped responses)

ESS (Employee Self Service):
- `GET  /attendance/me/days?from=YYYY-MM-DD&to=YYYY-MM-DD`
  - Returns base + effective status with precedence LEAVE > CORRECTION > BASE.
- `POST /attendance/me/corrections`
- `GET  /attendance/me/corrections?status=&limit=&cursor=`
- `POST /attendance/me/corrections/{correction_id}/cancel`

Admin (tenant-scoped listing):
- `GET /attendance/corrections?status=&branch_id=&from=&to=&limit=&cursor=`

Approvals are performed via workflow engine:
- `GET  /workflow/inbox`
- `POST /workflow/requests/{request_id}/approve`
- `POST /workflow/requests/{request_id}/reject`

## Notes on attendance summaries

The existing branch daily summary endpoint:
- `GET /api/v1/branches/{branch_id}/attendance/daily`

now accounts for overrides:
- `ON_LEAVE` excludes employees from the present count.
- Correction overrides can mark employees present/absent even if base rows disagree.
