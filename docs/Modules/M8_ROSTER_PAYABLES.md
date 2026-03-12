# M8 — Roster + Payables

## Scope
M8 adds the roster setup and payable-day reporting surfaces on top of the existing backend APIs.

### Routes
- HR
  - `/roster/shifts`
  - `/roster/default`
  - `/roster/assignments`
  - `/roster/overrides`
  - `/payables/admin`
- Self Service
  - `/payables/me`
- My Team
  - `/payables/team`

## Backend endpoints used
### Roster
- `GET /api/v1/roster/branches/{branch_id}/shifts?active_only=`
- `POST /api/v1/roster/branches/{branch_id}/shifts`
- `PATCH /api/v1/roster/shifts/{shift_template_id}`
- `GET /api/v1/roster/branches/{branch_id}/default-shift`
- `PUT /api/v1/roster/branches/{branch_id}/default-shift`
- `GET /api/v1/roster/employees/{employee_id}/assignments`
- `POST /api/v1/roster/employees/{employee_id}/assignments`
- `GET /api/v1/roster/employees/{employee_id}/overrides?from&to`
- `PUT /api/v1/roster/employees/{employee_id}/overrides/{day}`

### Payables
- `GET /api/v1/attendance/me/payable-days?from&to`
- `GET /api/v1/attendance/team/payable-days?from&to&depth=1|all`
- `GET /api/v1/attendance/admin/payable-days?from&to&branch_id&employee_id&limit&cursor`
- `POST /api/v1/attendance/payable/recompute`

### Supporting endpoints
- `GET /api/v1/hr/employees`
- `GET /api/v1/hr/employees/{employee_id}`

## Permissions
### Roster
- `roster:shift:read`
- `roster:shift:write`
- `roster:defaults:write`
- `roster:assignment:read`
- `roster:assignment:write`
- `roster:override:read`
- `roster:override:write`

### Payables
- `attendance:payable:read`
- `attendance:payable:team:read`
- `attendance:payable:admin:read`
- `attendance:payable:recompute`

## Scope rules
- `/roster/*` and `/payables/admin` fail closed without active company + branch scope.
- `/payables/me` and `/payables/team` stay actor-scoped and do not require manual branch selection.
- Assignments and overrides are employee-scoped because the backend does not expose tenant-wide list endpoints.

## UX notes
- Shift templates are branch-scoped and support create + patch.
- Default shift is a branch fallback used when no assignment or override exists.
- Overrides take precedence over assignments and branch default on that day.
- Admin payables use cursor pagination with `Load more`.
- Recompute only invalidates and refetches backend summaries; the UI does not fabricate outcomes.
- Client-side date bounds:
  - ESS/MSS payables: max 62 days
  - Admin reporting/recompute: max 366 days
  - Overrides list: max 31 days

## Known limits
- No delete or end-assignment endpoint exists.
- No override delete endpoint exists; overrides are upserts only.
- No org-unit filter exists for admin payables.
- No payables export endpoint exists.
- Team payables are aggregated client-side from flat backend rows.

## Tests
### Frontend unit + component
```bash
cd /Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend
npm run test
```

### Playwright smoke
```bash
cd /Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend
npm run test:e2e -- --project=chromium
```

## Canonical story covered
1. Create shift template.
2. Set branch default shift.
3. Assign employee to shift.
4. Apply a day override.
5. Recompute admin payables.
6. Inspect payable-day row produced by the backend.
