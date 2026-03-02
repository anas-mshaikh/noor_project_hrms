# M3 — Client Setup Pack (Bootstrap + Tenancy Console + IAM Console)

Last updated: 2026-03-02

This document summarizes what was delivered for Milestone 3 (M3) in the Noor HRMS **web** app (`frontend/`):

- Bootstrap flow (`/setup`) for first install
- Settings → Organization (Tenancy console)
- Settings → Access (IAM console)
- Enterprise frontend test kit (Vitest + RTL + MSW) and Docker test gating improvements
- Bugfixes found during M3 wiring (notably: IAM user detail `/undefined` + DS `EmptyState` Lucide icon crash)

Non-goals:
- No backend endpoint changes
- No mobile app changes


## 1) Major UX / Screens Delivered

### 1.1 Bootstrap (`/setup`)
Path: `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/setup/page.tsx`

Behavior:
- Unauthenticated-friendly page.
- Calls `POST /api/v1/bootstrap` to create:
  - tenant + company + branch
  - an admin user
- On success:
  - stores the session view via `useAuth.setFromSession(...)`
  - sets scope selection via `useSelection.setTenantId/companyId/branchId`
  - routes to `/scope?reason=bootstrap`
- Handles “already configured” (bootstrap rejected) with a dedicated state (no noisy toast).

Key UX rules:
- Errors use DS `ErrorState` with correlation reference when available.


### 1.2 Settings → Organization Console
Frame layout:
- `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/org/layout.tsx`
- Uses DS settings template (T6) and permission-aware subnav.

Routes:
- `/settings/org` (redirect)
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/org/page.tsx`
- Companies:
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/org/companies/page.tsx`
- Branches:
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/org/branches/page.tsx`
- Org Units:
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/org/org-units/page.tsx`
- Org Chart (viewer-only):
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/org/org-chart/page.tsx`
- Job Titles:
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/org/job-titles/page.tsx`
- Grades:
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/org/grades/page.tsx`

Implementation notes:
- Uses DS components: `PageHeader`, `DataTable`, `EmptyState`, `ErrorState`, `DSCard`.
- Create flows use Sheets.
- No “Edit” flows are implemented where backend does not support update endpoints (kept honest).
- Some screens require a selected company (via the scope picker); they fail-closed with an EmptyState prompting selection.


### 1.3 Settings → Access (IAM Console)
Frame layout:
- `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/access/layout.tsx`

Routes:
- `/settings/access` (redirect)
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/access/page.tsx`
- Users:
  - list: `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/access/users/page.tsx`
  - detail: `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/access/users/[userId]/page.tsx`
- Roles catalog (read-only):
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/access/roles/page.tsx`
- Permissions catalog (read-only):
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/access/permissions/page.tsx`

IAM role assignment UX:
- Tenant / Company / Branch scope toggle
- If tenancy reads are allowed, shows company/branch dropdown pickers
- Otherwise falls back to UUID inputs (still validates combinations)


## 2) Backend Endpoints Used (Web)

Source of truth: `backend/app/domains/*/router.py` (no backend changes required).

Bootstrap / Tenancy:
- `POST /api/v1/bootstrap`
- `GET /api/v1/tenancy/companies`
- `POST /api/v1/tenancy/companies`
- `GET /api/v1/tenancy/branches?company_id=...`
- `POST /api/v1/tenancy/branches`
- `GET /api/v1/tenancy/org-units?company_id=...&branch_id=...`
- `POST /api/v1/tenancy/org-units`
- `GET /api/v1/tenancy/org-chart?company_id=...&branch_id=...`
- `GET /api/v1/tenancy/job-titles?company_id=...`
- `POST /api/v1/tenancy/job-titles`
- `GET /api/v1/tenancy/grades?company_id=...`
- `POST /api/v1/tenancy/grades`

IAM:
- `GET /api/v1/iam/users?limit=&offset=&q=&status=` (returns `meta`)
- `POST /api/v1/iam/users`
- `GET /api/v1/iam/users/{user_id}`
- `PATCH /api/v1/iam/users/{user_id}`
- `GET /api/v1/iam/users/{user_id}/roles`
- `POST /api/v1/iam/users/{user_id}/roles`
- `DELETE /api/v1/iam/users/{user_id}/roles?role_code=...&company_id=&branch_id=...`
- `GET /api/v1/iam/roles`
- `GET /api/v1/iam/permissions`


## 3) Frontend Data Layer (API wrappers + types)

API wrappers:
- Tenancy: `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/features/tenancy/api/tenancy.ts`
- IAM: `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/features/iam/api/iam.ts`

Query keys:
- `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/features/tenancy/queryKeys.ts`
- `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/features/iam/queryKeys.ts`

Types:
- `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/lib/types.ts`

Meta support:
- `/api/v1/iam/users` returns `{ ok:true, data:[...], meta:{limit,offset,total} }`
- Frontend uses `apiEnvelope<T>()` to retain `meta`:
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/lib/api.ts`


## 4) Production-Safety Fixes Landed During M3

### 4.1 Prevent `/api/v1/iam/users/undefined*` (422) forever
Symptoms:
- Requests like:
  - `GET /api/v1/iam/users/undefined`
  - `GET /api/v1/iam/users/undefined/roles`
  - backend returns 422 because `{user_id}` must be a UUID.

Fix:
- Added UUID guard helpers:
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/lib/guards.ts`
- Hardened IAM user detail route:
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/access/users/[userId]/page.tsx`
  - Fail-closed UI (ErrorState) for missing/invalid params
  - React Query `enabled` gating: no request unless the param is a valid UUID
- Hardened Users list links:
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/access/users/page.tsx`
  - No link rendered if `id` is not a UUID.

Guardrail:
- Dev/test-only API client assertion to catch `undefined`/`null` path segments early:
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/lib/api.ts`


### 4.2 Fix DS `EmptyState` icon rendering crash in production builds
Symptom:
- Next `start` crash:
  - “Objects are not valid as a React child (found: object with keys {$$typeof, render, displayName})”

Root cause:
- Lucide icons are `forwardRef(...)` components at runtime (typeof === "object"), and `EmptyState` tried to render the component object as a child.

Fix:
- `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/components/ds/EmptyState.tsx`
  - Detect Lucide forwardRef components and instantiate them as `<Icon />`.


## 5) Enterprise Test Kit (Vitest + RTL + MSW)

Goal:
- Deterministic, production-like tests (React Query defaults match production).
- Domain-scoped MSW handlers.
- One canonical Vitest setup.

Canonical home:
- `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/test/`

Key files:
- Setup:
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/test/setup/vitest.setup.ts`
- MSW:
  - server: `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/test/msw/server.ts`
  - handlers index: `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/test/msw/handlers/index.ts`
  - envelope builders: `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/test/msw/builders/response.ts`
- Test utilities:
  - render wrapper: `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/test/utils/render.tsx`
  - router mocks: `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/test/utils/router.ts`
  - scope helpers: `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/test/utils/selection.ts`

Representative tests:
- IAM user detail fails closed on invalid UUID (no API call):
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/app/settings/access/users/[userId]/__tests__/page.test.tsx`
- DS EmptyState icon rendering:
  - `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend/src/components/ds/__tests__/EmptyState.test.tsx`


## 6) How to Run Tests (Local + Docker)

Local:
- Unit/component tests: `cd frontend && npm run test`
- E2E (Playwright): `cd frontend && npm run test:e2e`

Docker (full gate):
- From repo root:
  - `docker compose up --build --abort-on-container-exit --exit-code-from tests tests`

Skip tests (developer escape hatch):
- `SKIP_TESTS=1 docker compose up --build`

Note:
- Docker test container uses a dedicated frontend Dockerfile stage (no Next build tax for unit tests).


## 7) Known Issues / Follow-ups

- Login failures are almost always “DB is not fresh” (bootstrap already performed); reset volumes for a true first install.
- Onboarding routes are still UI-only and hidden in Client V0 nav.
- Consider adding a tiny “M3 admin runbook” (bootstrap/reset DB + first admin user) for faster onboarding.

