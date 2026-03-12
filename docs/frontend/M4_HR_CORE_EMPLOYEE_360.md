# M4 (Milestone 4) - HR Core + ESS + MSS

This document describes the current M4 user-facing functionality in the Noor HRMS web frontend, the backend endpoints it uses, required permissions, and how to run tests.

Repository: `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system`

## Scope

M4 delivers:

- HR Core (Admin/HR): Employee Directory, Create Employee, Employee 360 (Overview + Employment + Link User).
- ESS (Employee Self Service): My Profile (view/update), with guided "not linked" state.
- MSS (Manager Self Service): My Team list + member detail.

Non-goals:

- No new backend endpoints.
- No Documents/Requests/Payroll features (disabled tabs only).
- No bypassing scope selection (company selection is required for HR Core).

## Routes

HR Core:

- Employee Directory: `/hr/employees`
- Employee 360: `/hr/employees/[employeeId]`

ESS:

- My Profile: `/ess/me`

MSS:

- My Team: `/mss/team`
- Team member detail: `/mss/team/[employeeId]`

## Permissions (UI gating)

The UI is permission-aware based on `/api/v1/auth/me` and hides/disables actions accordingly.

HR Core:

- Read employee directory/detail: `hr:employee:read`
- Create employee, add employment record, link user: `hr:employee:write`

ESS:

- Read profile: `ess:profile:read`
- Update profile: `ess:profile:write`

MSS:

- Read team: `hr:team:read`

Optional (pickers and convenience UX):

- Tenancy pickers (branches/org-units dropdowns): `tenancy:read` or `tenancy:write`
- IAM user search for Link User tab: `iam:user:read` or `iam:user:write`

## Scope model (company required)

HR Core endpoints are company-scoped and the UI fail-closes when no company is selected:

- If `companyId` is missing in selection, `/hr/employees` and `/hr/employees/[employeeId]` render an `EmptyState` prompting the user to pick a company via `/scope`.

Selection source of truth:

- Scope picker + persistence: `frontend/src/lib/selection.ts`
- Scope page: `frontend/src/app/scope/page.tsx`

## Backend endpoints used (M4)

HR Core:

- `GET /api/v1/hr/employees`
- `POST /api/v1/hr/employees`
- `GET /api/v1/hr/employees/{employee_id}`
- `PATCH /api/v1/hr/employees/{employee_id}` (if/when used)
- `GET /api/v1/hr/employees/{employee_id}/employment`
- `POST /api/v1/hr/employees/{employee_id}/employment`
- `POST /api/v1/hr/employees/{employee_id}/link-user`

ESS:

- `GET /api/v1/ess/me/profile`
- `PATCH /api/v1/ess/me/profile`

MSS:

- `GET /api/v1/mss/team`
- `GET /api/v1/mss/team/{employee_id}`

Optional supporting endpoints (only when the user has permission):

- Tenancy catalogs:
  - `GET /api/v1/tenancy/branches?company_id=...`
  - `GET /api/v1/tenancy/org-units?company_id=...&branch_id=...`
- IAM user search (Link User tab):
  - `GET /api/v1/iam/users?q=...&limit=...&offset=...`

## UX + error handling conventions

All screens follow existing platform hardening:

- API envelope is respected: `{ ok: true, data }` / `{ ok: false, error }`
- Errors normalize through `ApiError` and are rendered via:
  - `frontend/src/lib/errorUx.ts` mappings
  - `frontend/src/components/ds/ErrorState`
  - `frontend/src/lib/toastApiError.ts` (toasts)
- Correlation/reference IDs are displayed in error UI when present.
- Dynamic route params are guarded using UUID parsing and React Query `enabled` gating to avoid `/undefined` or invalid UUID calls.

Guard helpers:

- `frontend/src/lib/guards.ts` (`parseUuidParam`, `isUuid`)

## Key flows

### HR - Employee Directory + Create Employee

Route: `/hr/employees`

- Uses DS list/table patterns and standard states: loading, empty, error.
- "Add employee" opens a Sheet and calls `POST /api/v1/hr/employees`.
- On success:
  - list query is invalidated
  - user is navigated to `/hr/employees/{employeeId}`

Implementation:

- Page: `frontend/src/app/hr/employees/page.tsx`
- API: `frontend/src/features/hr-core/api/hrCore.ts`
- Query keys: `frontend/src/features/hr-core/queryKeys.ts`

### HR - Employee 360

Route: `/hr/employees/[employeeId]`

Tabs:

- Overview (read-only summary)
- Employment (history + add record)
- Link user (links an IAM user to the employee)
- Documents/Payroll (disabled)

Implementation:

- Page: `frontend/src/app/hr/employees/[employeeId]/page.tsx`

#### Employment tab

- Loads `GET /api/v1/hr/employees/{id}/employment` when the Employment tab is active.
- Adds a record via `POST /api/v1/hr/employees/{id}/employment` (Sheet).
- Invalidates employee + employment history queries on success.

#### Link user tab (this answers "where do I link a user to an employee?")

The linking UX is in HR Core Employee 360, not in IAM "Roles & Access".

Steps (HR/Admin user):

1) Ensure a company is selected in `/scope`.
2) Open `/hr/employees` and click an employee.
3) Go to the "Link user" tab.
4) Link the IAM user:
   - if you have `iam:user:read`, search by email and select a result
   - otherwise paste the IAM user UUID
5) Click "Link user".

If the end-user sees `409 ess.not_linked` on `/ess/me`, that is expected until HR links them.

### ESS - My Profile

Route: `/ess/me`

- Loads profile via `GET /api/v1/ess/me/profile`.
- Updates allowed fields via `PATCH /api/v1/ess/me/profile`.
- If backend returns `409 ess.not_linked`, the page shows a guided "Account not linked" EmptyState with the backend reference/correlation id.

### MSS - My Team

Routes:

- `/mss/team` (list)
- `/mss/team/[employeeId]` (member detail)

Notes:

- Member detail renders a strict allow-list of fields (no dumping arbitrary JSON) to avoid accidentally showing sensitive data.
- Standard states: loading/empty/error/forbidden.

## Testing

Unit + component tests (Vitest + RTL + MSW):

```bash
cd frontend
npm run test
```

E2E smoke (Playwright):

```bash
cd frontend
npm run test:e2e
```

Docker (full gate, including Playwright profile):

```bash
# Unit/component + backend tests gate
docker compose up --build --abort-on-container-exit --exit-code-from tests tests

# E2E profile (Playwright container hitting frontend service)
docker compose --profile e2e up --build --abort-on-container-exit --exit-code-from frontend_e2e frontend_e2e
```

Test kit location:

- `frontend/src/test/` (MSW handlers, render helpers, setup)

## Known limitations / notes

- HR Core requires company scope selection; pages intentionally fail-closed when company is missing.
- Linking user to employee requires `hr:employee:write`.
- IAM user search in the Link User tab requires `iam:user:read` (otherwise the UI falls back to UUID input).

