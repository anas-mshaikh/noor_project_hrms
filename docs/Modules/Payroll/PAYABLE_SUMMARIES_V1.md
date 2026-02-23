# Payable Summaries v1 (Payroll-ready Day Outputs)

Milestone 8 introduces a deterministic, materialized "payable day summary" per
employee-business day. The goal is to provide a payroll-ready dataset that:

- Combines roster schedule (expected minutes) with attendance worked minutes.
- Respects leave/correction precedence for both status and minutes.
- Is safe in a multi-tenant enterprise environment (tenant-scoped, RBAC
  enforced, deterministic).

The summaries are stored in `attendance.payable_day_summaries` and are
computed/upserted by the service `PayableSummaryComputeService`.

## Data Model

### `attendance.payable_day_summaries`

One row per `(tenant_id, employee_id, day)`:

- `tenant_id` (FK `tenancy.tenants.id`)
- `branch_id` (FK `tenancy.branches.id`)
- `employee_id` (FK `hr_core.employees.id`)
- `day` (`date`)
- `shift_template_id` (FK `roster.shift_templates.id`, nullable)
- `day_type` (enum-like text):
  - `WORKDAY`, `WEEKOFF`, `HOLIDAY`, `ON_LEAVE`, `UNSCHEDULED`
- `presence_status` (enum-like text):
  - `PRESENT`, `ABSENT`, `N_A`
- `expected_minutes` (int, default `0`)
- `worked_minutes` (int, default `0`)
- `payable_minutes` (int, default `0`)
- `late_minutes` (int, placeholder, default `0`)
- `overtime_minutes` (int, placeholder, default `0`)
- `anomalies_json` (jsonb, nullable)
- `source_breakdown` (jsonb, nullable)
- `computed_at` (timestamptz, default `now()`)

Constraints / indexes:

- Unique: `(tenant_id, employee_id, day)`
- Index: `(tenant_id, branch_id, day)`
- Index: `(tenant_id, employee_id, day)`

## Inputs & Precedence Rules

Payable summaries depend on these existing sources:

- Roster schedule:
  - `roster.roster_overrides`
  - `roster.shift_assignments`
  - `roster.branch_defaults`
  - `roster.shift_templates`
- Attendance base rollup:
  - `attendance.attendance_daily.total_minutes`
  - `attendance.attendance_daily.source_breakdown`
  - `attendance.attendance_daily.has_open_session`
- Attendance overrides (existing precedence model):
  - `attendance.day_overrides`
- Branch calendar rules (canonical in v1):
  - `leave.weekly_off` (must have 7 rows per branch)
  - `leave.holidays` (branch-specific + global)

### Day Type Resolution

Day type is resolved per `(employee, day)` with this v1 precedence:

1. `attendance.day_overrides.status == 'ON_LEAVE'` -> `ON_LEAVE`
2. `roster.roster_overrides.override_type == 'WEEKOFF'` -> `WEEKOFF`
3. `roster.roster_overrides.override_type == 'WORKDAY'` -> `WORKDAY`
4. Holiday (`leave.holidays`) -> `HOLIDAY`
5. Weekly off (`leave.weekly_off`) -> `WEEKOFF`
6. Default -> `WORKDAY`

If day type is `WORKDAY` but no shift can be resolved (override/assignment/default
missing), we downgrade to `UNSCHEDULED` with `expected_minutes=0`.

Notes:

- Roster override `SHIFT_CHANGE` does not change the day type; it only changes
  the shift template for that workday.
- `ON_LEAVE` always wins over roster overrides and calendar rules.

### Expected Minutes

Expected minutes are computed only when the day is a workday and a shift is
resolved.

- Uses `roster.shift_templates.start_time/end_time/break_minutes`.
- Overnight shifts are supported: `end_time <= start_time` implies "next day".

### Worked Minutes (Override-aware)

Worked minutes use the existing attendance precedence model (Milestone 7):

1. If `ON_LEAVE` -> `worked_minutes = 0`
2. Else if newest correction override payload includes `override_minutes` ->
   `worked_minutes = override_minutes`
3. Else if correction status is `ABSENT_OVERRIDE` -> `worked_minutes = 0`
4. Else base minutes from `attendance.attendance_daily.total_minutes` (NULL treated
   as 0)

`source_breakdown` is copied from `attendance.attendance_daily.source_breakdown`
for traceability.

### Payable Minutes (v1 policy)

v1 is conservative and produces *payable minutes only on workdays*:

- `ON_LEAVE`, `HOLIDAY`, `WEEKOFF`, `UNSCHEDULED`:
  - `presence_status='N_A'`
  - `payable_minutes=0`
- `WORKDAY`:
  - if `worked_minutes <= 0` -> `presence_status='ABSENT'`, `payable_minutes=0`
  - else -> `presence_status='PRESENT'`
  - `payable_minutes = min(worked_minutes, expected_minutes)` when expected > 0,
    else payable = worked

Placeholders:

- `late_minutes` and `overtime_minutes` are reserved for future enhancements.

### Calendar Enforcement (Fail-closed)

The compute service enforces that `leave.weekly_off` is configured for the
branch. If the branch does not have 7 rows (weekday 0..6), compute fails with:

- `attendance.payable.calendar_missing` (HTTP 400)

## APIs (All `/api/v1`, JSON envelope)

### ESS (Self)

- `GET /api/v1/attendance/me/payable-days?from=YYYY-MM-DD&to=YYYY-MM-DD`
  - Permission: `attendance:payable:read`
  - Behavior: compute-on-demand for small ranges (bounded), then return rows.

### MSS (Team)

- `GET /api/v1/attendance/team/payable-days?from=YYYY-MM-DD&to=YYYY-MM-DD&depth=1|all`
  - Permission: `attendance:payable:team:read`
  - Behavior: resolves team directory (MSS graph), compute-on-demand, returns a
    flat list.

### HR/Admin Reporting

- `GET /api/v1/attendance/admin/payable-days?from=YYYY-MM-DD&to=YYYY-MM-DD&branch_id=&employee_id=&limit=&cursor=`
  - Permission: `attendance:payable:admin:read`
  - Behavior: reads materialized rows (does not compute).

- `POST /api/v1/attendance/payable/recompute`
  - Permission: `attendance:payable:recompute`
  - Body: `{ "from": "...", "to": "...", "branch_id"?: "...", "employee_ids"?: ["..."] }`
  - Behavior: synchronous recompute in v1 (upsert).

Range limits (v1):

- ESS/MSS compute-on-demand uses a small safety bound (default 62 days).
- Admin recompute endpoint allows larger ranges (default 366 days) but requires
  either `branch_id` or explicit `employee_ids` to avoid recomputing an entire
  tenant accidentally.

## Error Codes

- `attendance.payable.invalid_range` (400)
- `attendance.payable.calendar_missing` (400)
- `attendance.payable.employee.not_found` (404)
- `attendance.payable.recompute.forbidden` (403)
- `iam.scope.mismatch` (400) for branch-scoped actors attempting to cross-branch

## Example Response

`GET /api/v1/attendance/me/payable-days?from=2026-02-18&to=2026-02-18`

```json
{
  "ok": true,
  "data": {
    "items": [
      {
        "day": "2026-02-18",
        "employee_id": "00000000-0000-0000-0000-000000000000",
        "branch_id": "00000000-0000-0000-0000-000000000000",
        "shift_template_id": "00000000-0000-0000-0000-000000000000",
        "day_type": "WORKDAY",
        "presence_status": "PRESENT",
        "expected_minutes": 480,
        "worked_minutes": 300,
        "payable_minutes": 300,
        "anomalies_json": {"has_open_session": false},
        "source_breakdown": {"MANUAL_WEB": 300},
        "computed_at": "2026-02-18T10:00:00Z"
      }
    ]
  }
}
```

