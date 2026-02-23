# Roster v1 (Shifts & Rostering)

Milestone 8 introduces a scheduling layer under the `roster` schema. This
provides:

- Branch-scoped shift templates (start/end/break).
- A branch default shift fallback.
- Effective-dated employee shift assignments.
- Per-employee per-day overrides (shift change / force weekoff / force workday).

This module is intentionally "policy-light" in v1. It produces deterministic
schedule data for downstream systems (e.g., payable summaries, payroll).

## Data Model

### `roster.shift_templates`

Reusable shift definitions per branch.

Key columns:

- `tenant_id` (FK `tenancy.tenants.id`)
- `branch_id` (FK `tenancy.branches.id`)
- `code` (unique per tenant+branch)
- `start_time`, `end_time` (`time`)
- `break_minutes` (`int`, default `0`)
- `grace_minutes` (`int`, placeholder, default `0`)
- `min_full_day_minutes` (`int`, placeholder, nullable)
- `is_active` (`bool`, default `true`)
- `created_by_user_id` (FK `iam.users.id`, nullable)
- `created_at`, `updated_at`

Constraints / indexes:

- Unique: `(tenant_id, branch_id, code)`
- Index: `(tenant_id, branch_id, is_active)`
- `updated_at` maintained by `public.set_updated_at()` trigger.

Overnight support:

- The DB allows any time ranges. Overnight shift handling is implemented in
  application code:
  - If `end_time <= start_time`, the shift is treated as ending on the next day.

### `roster.branch_defaults`

Optional default shift per branch. Used when an employee has no assignment and
no per-day override provides a shift.

Key columns:

- Composite primary key: `(tenant_id, branch_id)`
- `default_shift_template_id` (FK `roster.shift_templates.id`)
- `created_at`, `updated_at` (triggered)

### `roster.shift_assignments`

Effective-dated employee shift assignment history.

Key columns:

- `employee_id` (FK `hr_core.employees.id`)
- `branch_id` (snapshot branch from employee current employment at creation time)
- `shift_template_id` (FK `roster.shift_templates.id`)
- `effective_from` (`date`)
- `effective_to` (`date`, nullable)
- `created_by_user_id` (nullable)
- `created_at`, `updated_at` (triggered)

Constraints / indexes:

- One active row per employee: unique `(tenant_id, employee_id)` where
  `effective_to IS NULL`.
- Indexes:
  - `(tenant_id, employee_id, effective_from)`
  - `(tenant_id, branch_id, effective_from)`

Overlap validation:

- The service rejects overlapping effective date ranges with
  `roster.assignment.overlap` (409). It is enforced both by application
  validation and the active-row unique index.

### `roster.roster_overrides`

Per-employee per-day overrides.

Key columns:

- `employee_id` (FK `hr_core.employees.id`)
- `branch_id` (snapshot from current employment at creation time)
- `day` (`date`)
- `override_type`:
  - `SHIFT_CHANGE`: use `shift_template_id` for that day.
  - `WEEKOFF`: force a week off (no shift).
  - `WORKDAY`: force a workday (optional `shift_template_id`; otherwise fallback).
- `shift_template_id` (nullable; required for `SHIFT_CHANGE`)
- `notes` (nullable)
- `created_by_user_id` (nullable)
- `created_at`, `updated_at` (triggered)

Constraints / indexes:

- Unique: `(tenant_id, employee_id, day)`
- Index: `(tenant_id, branch_id, day)`

## Shift Minutes (Expected Minutes)

Expected minutes are computed by the service helper:

1. Convert `start_time` and `end_time` to minutes since midnight.
2. Reject `start_time == end_time` (v1 does not allow ambiguous "24h" shifts).
3. If `end_time <= start_time`, add 24h to `end_time` (overnight shift).
4. `duration = end - start`
5. Validate `0 <= break_minutes <= duration`
6. `expected = duration - break_minutes`

Notes:

- The DB does not enforce the above rules; they are enforced by the API/service.
- Future enhancement placeholders include grace/min_full_day rules.

## Schedule Resolution (Used by Payable Summaries)

When a schedule needs to be resolved for `(employee_id, day)` (for workdays),
the selection order is:

1. `roster.roster_overrides`:
   - `SHIFT_CHANGE` uses `shift_template_id`.
   - `WORKDAY` uses `shift_template_id` if present, otherwise fall through.
2. `roster.shift_assignments` row covering the `day`.
3. `roster.branch_defaults.default_shift_template_id`.
4. No shift resolved -> "unscheduled" (expected minutes = 0).

## APIs (All `/api/v1`, JSON envelope)

Router prefix: `/api/v1/roster`

### Shift templates

- `POST /roster/branches/{branch_id}/shifts`
  - Permission: `roster:shift:write`
- `GET /roster/branches/{branch_id}/shifts?active_only=1`
  - Permission: `roster:shift:read`
- `PATCH /roster/shifts/{shift_template_id}`
  - Permission: `roster:shift:write`

### Branch default shift

- `PUT /roster/branches/{branch_id}/default-shift`
  - Permission: `roster:defaults:write`
- `GET /roster/branches/{branch_id}/default-shift`
  - Permission: `roster:shift:read`

### Assignments

- `POST /roster/employees/{employee_id}/assignments`
  - Permission: `roster:assignment:write`
- `GET /roster/employees/{employee_id}/assignments`
  - Permission: `roster:assignment:read`

### Overrides

- `PUT /roster/employees/{employee_id}/overrides/{day}`
  - Permission: `roster:override:write`
- `GET /roster/employees/{employee_id}/overrides?from=YYYY-MM-DD&to=YYYY-MM-DD`
  - Permission: `roster:override:read`

## Permissions (RBAC)

Roster v1 uses these permission codes:

- `roster:shift:read`, `roster:shift:write`
- `roster:assignment:read`, `roster:assignment:write`
- `roster:override:read`, `roster:override:write`
- `roster:defaults:write`

Default role mapping (seeded, still enforced by service code):

- `ADMIN`: all roster permissions
- `HR_ADMIN`: all roster permissions

## Audit Events

The following audit actions are written (minimal payloads; no PII):

- `roster.shift.create`
- `roster.shift.patch`
- `roster.default.set`
- `roster.assignment.create`
- `roster.override.upsert`

## Future Extensions (Placeholders)

The data model includes placeholders for future enhancements:

- Grace windows and partial-day rules.
- Overtime and late policies (computed in payable summaries, not roster).
- Schedule by org unit / job title / grade (not in v1).

