# Leave Management v1 (Milestone 3)

This repo includes a first-class **Leave** domain (`leave.*`) that integrates with the **Workflow Engine v1** for approvals.

Design principle:
- Leave stores the canonical business facts (dates, leave type, requested_days, status, ledger, calendar days).
- Workflow stores the approval process (steps/assignees/decisions) and in-app notifications.
- The two are linked via:
  - `workflow.requests.entity_type = "leave.leave_request"`
  - `workflow.requests.entity_id = leave.leave_requests.id`

## Database

Schema: `leave`

Core tables:
- `leave.leave_types`: tenant-scoped catalog (ANNUAL, SICK, ...)
- `leave.leave_policies`: effective-dated policy container (optionally scoped to company/branch)
- `leave.leave_policy_rules`: policy x leave_type rules (entitlements, allow_half_day, attachment overrides)
- `leave.employee_leave_policy`: effective-dated assignment (one active row per employee)
- `leave.leave_requests`: domain leave request record linked to `workflow.requests`
- `leave.leave_request_days`: exploded day rows for overlap checks + calendars
- `leave.leave_ledger`: immutable balance ledger (allocations + consumption)
- `leave.weekly_off`: REQUIRED configuration per branch (7 rows, weekday 0..6)
- `leave.holidays`: global and branch holidays

Attendance integration foundation:
- `attendance.day_overrides`: written on approval to mark countable leave days as `ON_LEAVE`.

## Workflow integration

Leave uses workflow request type code:
- `LEAVE_REQUEST` (seeded via Alembic)

For Leave submissions to work, the tenant/company must have an **active** workflow definition for `LEAVE_REQUEST`.
Common v1 definition:
- step 0: `MANAGER`
(Optionally add an HR step later with `ROLE(HR_ADMIN)`.)

When a workflow request transitions to terminal status, the workflow engine invokes a domain hook based on `entity_type`.
For leave:
- `approved`:
  - inserts a ledger consumption row (`source_type='LEAVE_REQUEST'`, `delta_days=-requested_days`) idempotently
  - writes `attendance.day_overrides` for each countable day (idempotent)
  - updates `leave.leave_requests.status = 'APPROVED'`
- `rejected`: updates leave request to `REJECTED`
- `cancelled`: updates leave request to `CANCELED`

All side-effects happen inside the same DB transaction as the workflow transition.

## Permissions (colon-style)

Seeded via Alembic and mapped to default roles:
- `leave:type:read`, `leave:type:write`
- `leave:policy:read`, `leave:policy:write`
- `leave:allocation:write`
- `leave:balance:read`
- `leave:request:submit`, `leave:request:read`
- `leave:team:read`
- `leave:admin:read`

## API (all under `/api/v1`, enveloped responses)

ESS (Employee Self Service):
- `GET  /leave/me/balances?year=YYYY`
- `GET  /leave/me/requests?status=&limit=&cursor=`
- `POST /leave/me/requests`
- `POST /leave/me/requests/{leave_request_id}/cancel`

MSS (Manager):
- `GET /leave/team/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD&depth=1|all&branch_id=...`
Approvals are performed via workflow:
- `GET  /workflow/inbox`
- `POST /workflow/requests/{request_id}/approve`
- `POST /workflow/requests/{request_id}/reject`

HR Admin:
- `GET/POST /leave/types`
- `GET/POST /leave/policies`
- `POST     /leave/policies/{policy_id}/rules`
- `POST     /leave/employees/{employee_id}/policy`
- `POST     /leave/allocations`
- Calendar config (required for submissions):
  - `GET/PUT /leave/calendar/weekly-off?branch_id=...`
  - `GET/POST /leave/calendar/holidays?...`
- Reports:
  - `GET /leave/reports/usage?year=YYYY&branch_id=&leave_type_code=`

## Required setup (v1)

Leave submission requires:
1) Weekly off configured for the employee’s employment branch (`leave.weekly_off` must have weekdays 0..6).
   - Default: branches are auto-initialized to **Fri+Sat off** (Saudi weekend). You can override per branch via API.
2) A leave policy assigned to the employee (effective-dated).
3) An active workflow definition for request type `LEAVE_REQUEST`.
4) Sufficient balance in `leave.leave_ledger` unless `leave_types.allow_negative_balance=true`.
