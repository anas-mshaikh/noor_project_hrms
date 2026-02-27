# Frontend Current State (Web / Next.js)

Last updated: 2026-02-23

This document describes the current state of the **web frontend** found in `frontend/`.
It covers: routes/screens, navigation shell (top bar + sidebar), styling/theme, animations,
backend API wiring coverage, and known broken areas.

Note: This does **not** cover the React Native app in `mobile-application/`.

See also:
- Production-readiness audit (V0 checklist vs current implementation):
  `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/docs/frontend/V0_PRODUCTION_READINESS_AUDIT.md`


## 1) Tech Stack & App Architecture

- Framework: Next.js App Router (Next 16) with client-heavy pages (`"use client"`).
- React: React 19.
- Data fetching: TanStack React Query (`@tanstack/react-query`).
- State:
  - Auth session (user/roles/permissions/scope) persisted via Zustand:
    `frontend/src/lib/auth.ts`
  - Context selection (tenant/company/branch/camera) persisted via Zustand:
    `frontend/src/lib/selection.ts`
- API client: `frontend/src/lib/api.ts`
  - Same-origin: calls `/api/v1/*` which is handled by the Next.js BFF proxy route
    `frontend/src/app/api/v1/[...path]/route.ts`.
  - Tokens are stored as **HttpOnly cookies** (`noor_access_token`,
    `noor_refresh_token`) set by the BFF. The browser does not store tokens in
    localStorage.
  - Adds scope headers from persisted selection: `X-Tenant-Id`, `X-Company-Id`,
    `X-Branch-Id` (forwarded by the BFF to backend).
  - On 401: BFF performs refresh rotation and retries once when safe.
  - Extracts and surfaces correlation id (`X-Correlation-Id`) in structured API
    errors; redirects to `/scope` on `iam.scope.*` fail-closed errors.
- I18n: local JSON dictionaries with cookie + RTL support:
  - `frontend/src/lib/i18n.tsx`
  - `frontend/src/lib/locale.ts`
  - Locale selection via TopBar profile menu and Settings page.


## 2) Global Shell (Layout, Navigation, Context Picker)

Global wrapper: `frontend/src/components/shell/Shell.tsx`

Composition:
- Background: `ShellBackdrop`
  - Dark gradient + violet/fuchsia glow + subtle noise overlay.
- Top bar: `TopBar`
  - Sticky header.
  - Logo navigates to active module home.
  - Desktop module tabs are permission-gated; placeholder modules are hidden in
    Client V0 (Tasks/Inbox/Notes).
  - Right-side actions:
    - Notifications (toast: Coming soon)
    - Help (toast: Coming soon)
    - Profile dropdown (language switcher + Settings link + sign out; Profile action
      is Coming soon)
- Sidebar (desktop): `SidebarRail`
  - Icon-only rail driven by active module's sidebar items.
  - Hover tooltip with title/description.
  - Small hover motion (Framer Motion) unless reduced-motion.
  - Context shortcut at bottom:
    - Opens a Sheet with the `StorePicker` (Tenant -> Company -> Branch -> Camera).
    - Optional debug: shows branch_id/camera_id when
      `NEXT_PUBLIC_SHOW_DEBUG_IDS=true` or dev mode.
- Mobile: `MobileMenuSheet`
  - Opened via menu icon in top bar.
  - Module switcher grid + active module items + context picker at bottom.

Navigation configuration: `frontend/src/config/navigation.ts`
- Special UX rules:
  - Sidebar "Videos" is considered active for `/videos`, `/jobs/*`, `/reports/*`.
  - Sidebar "Setup" is considered active for `/setup` and `/cameras/*`
    (Calibration).

RTL support:
- Global HTML `dir` is set based on locale.
- CSS adjusts shell direction:
  - `frontend/src/app/globals.css` includes `.shell-main` and `.topbar-actions` RTL
    rules.


## 3) Visual Design System (Styling, Colors, Fonts)

Global CSS: `frontend/src/app/globals.css`
- Tailwind v4 via `@import "tailwindcss";`
- Theme tokens via CSS variables (OKLCH).
- Dark mode is default (`<html class="dark">` in `frontend/src/app/layout.tsx`).
- "Purple glass" look:
  - Primary accent: violet/fuchsia (primary + ring).
  - Many surfaces: semi-transparent whites (`bg-white/[0.03..0.08]`) +
    `backdrop-blur-xl`.
  - Borders: `border-white/10` / `ring-white/10`.

Fonts:
- `globals.css` maps `--font-sans` to `--font-geist-sans` and `--font-mono` to
  `--font-geist-mono`.
- Current code does **not** define the Geist font variables via `next/font`
  (no Geist import found).
- `frontend/README.md` claims Geist is used, but the app layout does not implement
  it yet.
- Practical effect: typography likely falls back to default font stack; `font-mono`
  may also be fallback.

UI primitives:
- Small shadcn-like component set under `frontend/src/components/ui/` (Radix +
  Tailwind + cva):
  - Button, Card, Input, Label, Table, Dialog, DropdownMenu, Tabs, Tooltip, Sheet,
    Skeleton, Badge, Separator.

Toasts:
- Sonner toaster in `frontend/src/app/providers.tsx`, top-right, rich colors.


## 4) Animations & Motion

Motion libs present:
- Framer Motion: actively used.
- gsap, @react-spring/web: installed but not currently used (as of this snapshot).

Shell motion:
- Sidebar rail icon hover uses Framer Motion with small translate/rotate/scale:
  - `frontend/src/components/shell/SidebarRail.tsx`
- Reduced-motion respected via:
  - `frontend/src/lib/useReducedMotion.ts` (shell)
  - HR suite also has its own reduced-motion hook and variants.

HR suite motion:
- Page mount fade and stagger-in for lists/cards:
  - `frontend/src/features/hr/components/layout/HrPageShell.tsx`
  - `frontend/src/features/hr/lib/motion.ts`


## 5) Auth + Scope + "Context Picker" UX

Login:
- Route: `/login`
- File: `frontend/src/app/login/page.tsx`
- Calls: `POST /api/v1/auth/login`
- On success:
  - The BFF sets HttpOnly cookies (`noor_access_token`, `noor_refresh_token`).
  - Frontend stores only a redacted session (user/roles/permissions/scope).
  - Selection defaults (tenant/company/branch) are derived from session scope.
  - Redirects to `/dashboard`.

Auth bootstrap:
- Component: `frontend/src/components/AuthBootstrap.tsx`
- Mounted from: `frontend/src/app/providers.tsx`
- Calls: `GET /api/v1/auth/me` to hydrate auth session on reloads (cookies-based).

Context picker:
- Component: `frontend/src/components/StorePicker.tsx`
- Calls:
  - `GET /api/v1/tenancy/companies`
  - `GET /api/v1/tenancy/branches?company_id=...`
  - `GET /api/v1/branches/{branch_id}/cameras`
- Tenant selection UI shows IDs from session scope `allowed_tenant_ids` (not tenant
  names).


## 6) Route/Screens Inventory (What Exists Today)

Legend:
- WORKING: calls backend endpoints that exist.
- BROKEN (API mismatch): UI exists but calls paths not present in backend OpenAPI.
- MOCK/UI-only: uses mock data; no backend calls.
- PLACEHOLDER: uses `PlaceholderPage` scaffold.

### Attendance module
- `/dashboard` (WORKING)
  - Branch-scoped daily summary dashboards.
  - Calls: `GET /api/v1/branches/{branch_id}/attendance/daily`
- `/setup` (PARTIAL)
  - If not signed in: bootstrap tenant/company/branch + admin (dev flow).
    - Calls: `POST /api/v1/bootstrap`
  - If signed in: create camera for selected branch.
    - Calls: `POST /api/v1/branches/{branch_id}/cameras`
  - Links to calibration: `/cameras/{cameraId}/calibration` (see broken note below)
- `/employees` (WORKING)
  - HR employee directory + create employee + face enrollment + mobile provisioning.
  - Calls:
    - `GET /api/v1/hr/employees?branch_id=...`
    - `POST /api/v1/hr/employees`
    - `POST /api/v1/branches/{branch_id}/employees/{employee_id}/faces/register`
      (multipart)
    - `POST /api/v1/branches/{branch_id}/faces/recognize` (multipart)
    - `GET /api/v1/branches/{branch_id}/mobile/accounts`
    - `POST /api/v1/branches/{branch_id}/employees/{employee_id}/mobile/provision`
    - `POST /api/v1/branches/{branch_id}/employees/{employee_id}/mobile/revoke`
    - `POST /api/v1/mobile/resync/{firebase_uid}`
- `/videos` (BROKEN in one step)
  - Uses `UploadWizard` for:
    - Init video: `POST /api/v1/branches/{branch_id}/videos/init` (OK)
    - Upload PUT to returned endpoint (OK)
    - Finalize: POST returned endpoint (OK)
    - Create job: currently calls `POST /api/v1/videos/{video_id}/jobs` (BROKEN)
      - Backend expects:
        `POST /api/v1/branches/{branch_id}/videos/{video_id}/jobs`
- `/admin/import` (WORKING)
  - Upload XLSX and publish dataset.
  - Calls:
    - `POST /api/v1/branches/{branch_id}/imports`
    - `POST /api/v1/branches/{branch_id}/imports/{dataset_id}/publish`

### Job/Report/Calibration (attendance "videos" sub-flow)
- `/jobs/{jobId}` (BROKEN)
  - Calls:
    - `GET /api/v1/jobs/{job_id}`
    - `POST /api/v1/jobs/{job_id}/cancel`
    - `POST /api/v1/jobs/{job_id}/retry`
  - Backend expects all job endpoints under:
    - `/api/v1/branches/{branch_id}/jobs/...`
- `/reports/{jobId}` (BROKEN)
  - Calls:
    - `GET /api/v1/jobs/{job_id}/attendance`
    - `GET /api/v1/jobs/{job_id}/events`
    - `GET /api/v1/jobs/{job_id}/metrics/hourly`
    - `GET /api/v1/jobs/{job_id}/artifacts`
    - `GET /api/v1/artifacts/{artifact_id}/download`
  - Backend expects:
    - `/api/v1/branches/{branch_id}/jobs/{job_id}/...`
    - `/api/v1/branches/{branch_id}/artifacts/{artifact_id}/download`
- `/cameras/{cameraId}/calibration` (BROKEN)
  - Calls:
    - `GET /api/v1/cameras/{camera_id}`
    - `PUT /api/v1/cameras/{camera_id}/calibration`
  - Backend expects:
    - `/api/v1/branches/{branch_id}/cameras/{camera_id}`
    - `/api/v1/branches/{branch_id}/cameras/{camera_id}/calibration`

Also broken inside a component:
- `EventsTable` snapshot preview (BROKEN):
  - Calls: `GET /api/v1/events/{event_id}/snapshot`
  - Backend expects:
    `GET /api/v1/branches/{branch_id}/events/{event_id}/snapshot`

### HR module
- `/hr` (PARTIAL)
  - Uses backend for openings list (branch-scoped), but also shows mock cards/activity/
    onboarding counters.
  - Has multiple "Coming soon" actions (run screening, upload resumes, insights
    review).
- `/hr/openings` (PARTIAL)
  - Calls backend openings list.
  - Still uses mock data for "Top by volume" / "Recent runs" style panels.
  - "Filters" button is Coming soon.
- `/hr/openings/new` (WORKING)
  - Creates opening (branch-scoped).
- `/hr/openings/{id}` (PARTIAL but mostly WORKING)
  - Uses backend for opening/resume ingestion/embedding/pipeline/runs.
  - Some "insights" or run-results panels still mix mock data.
- `/hr/pipeline` (WORKING)
  - Branch-scoped pipeline with Kanban board.
  - Uses backend:
    - openings list
    - pipeline stages
    - applications (and stage move)
- `/hr/runs` (MOCK/UI-only)
  - Uses `HR_RUNS` mock data (no backend list call).
- `/hr/runs/{runId}` (WORKING)
  - Uses backend run read + results + cancel/retry + explanations enqueue.
- `/hr/onboarding` (MOCK/UI-only)
  - Uses mock onboarding employees; no backend.
- `/hr/onboarding/{employeeId}` (MOCK/UI-only)
  - Mock checklist + docs; no backend.

### Tasks / Inbox / Notes / Settings
- Tasks:
  - `/tasks` (PLACEHOLDER)
  - `/tasks/team` (PLACEHOLDER)
  - `/tasks/approvals` (PLACEHOLDER)
- Inbox:
  - `/inbox` (PLACEHOLDER)
  - `/inbox/groups` (PLACEHOLDER)
  - `/inbox/mentions` (PLACEHOLDER)
- Notes:
  - `/notes` (PLACEHOLDER)
  - `/notes/templates` (PLACEHOLDER)
  - `/notes/library` (PLACEHOLDER)
- Settings:
  - `/settings` (WORKING - language selection only)
  - `/settings/org` (PLACEHOLDER)
  - `/settings/access` (PLACEHOLDER)
  - `/settings/integrations` (PLACEHOLDER)


## 7) Placeholder and "Coming soon" Inventory

Placeholder pages (12 routes) use:
- `frontend/src/components/shell/PlaceholderPage.tsx`

Coming-soon UX patterns:
- Many buttons do `toast("Coming soon", { description: ... })` instead of calling
  backend.
- Common sources:
  - Shell: notifications/help/profile actions (`TopBar`)
  - HR overview actions and AI insights actions
  - HR runs list actions
  - HR onboarding actions
  - Pipeline card "Notes coming soon"
  - Candidate drawer actions (shortlist/reject/etc)


## 8) Backend API Coverage (Web Frontend vs Backend OpenAPI)

Snapshot method:
- Backend OpenAPI paths generated from backend app: 172 `/api/v1/*` paths.
- Frontend scan: literal references to `/api/v1/...` in `frontend/src/`, normalized for
  `{id}` segments and `${var}`.

Results:
- Backend `/api/v1/*` paths: 172
- Frontend referenced API paths (normalized unique): 54
- Matched backend paths after normalization: 41
- Frontend references not present in backend OpenAPI: 13
- Backend endpoints not referenced by frontend literals: 131

Frontend-referenced paths missing in backend OpenAPI (normalized):
- `/api/v1/jobs/{job_id}` + subpaths (should be `/api/v1/branches/{branch_id}/jobs/...`)
- `/api/v1/artifacts/{artifact_id}/download` (should be branch-scoped)
- `/api/v1/events/{event_id}/snapshot` (should be branch-scoped)
- `/api/v1/cameras/{camera_id}` + `/calibration` (should be branch-scoped)
- `/api/v1/videos/{video_id}/jobs` (should be branch-scoped)

Interpretation:
- The web frontend currently uses a subset of the backend:
  - CCTV attendance processing admin flows (videos/jobs/reports, cameras calibration,
    imports)
  - HR screening module (openings, resumes, screening runs, pipeline)
- Newer HRMS backend domains (workflow, DMS HR ops, onboarding v2, profile change,
  roster/payable, payroll) are largely **not yet wired** in this web frontend.


## 9) Known UX/Tech Debt Notes (As-Is Observations)

- Fonts:
  - Global CSS expects Geist font variables, but there is no Geist font setup in code.
- Route protection:
  - Pages are accessible without auth; failures occur when API calls 401 and api
    client redirects.
  - No Next.js middleware-based auth gating is present.
- API base URL and security:
  - All browser API calls go through the Next.js BFF route handler:
    `frontend/src/app/api/v1/[...path]/route.ts`.
  - Backend proxy target is configured via `API_PROXY_TARGET` (server-only env var).
- Unused/legacy code:
  - `frontend/src/components/hr/*` appears unused (older HR widgets).
  - `frontend/src/lib/motion.ts` appears unused (HR uses `features/hr/lib/motion.ts`).
  - Dependencies `gsap` and `@react-spring/web` appear installed but unused.


## 10) Immediate Fix List (If We Want to Stabilize the Demo)

1) Fix branch-scoping mismatches in Attendance job/report/calibration flows:
- Update frontend calls to use:
  - `/api/v1/branches/{branch_id}/jobs/...`
  - `/api/v1/branches/{branch_id}/artifacts/...`
  - `/api/v1/branches/{branch_id}/events/...`
  - `/api/v1/branches/{branch_id}/cameras/...`
  - `/api/v1/branches/{branch_id}/videos/{video_id}/jobs`
- Source of truth for `branch_id`: `useSelection().branchId`

2) Decide whether jobs/reports should be navigable without branch selection:
- Either enforce "select branch first" UX on those pages,
- Or embed branch_id in the route `/branches/{branch_id}/jobs/{job_id}` (bigger route
  change).

3) Add font setup (optional):
- Implement `next/font` in `frontend/src/app/layout.tsx` or remove Geist vars from
  CSS.
