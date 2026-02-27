<!--
Frontend production-readiness audit for Client V0.

This doc is intentionally concrete: every "gap" should link to a file path so
engineers can implement fixes quickly.
-->

# Frontend V0 Production Readiness Audit (Web / Next.js)

Last updated: 2026-02-23

This document audits the current **web frontend** (`frontend/`) against the
production-readiness checklist in:

- `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/docs/V0_production.md`

It summarizes what is already implemented, what is missing, and a prioritized
hardening backlog (P0/P1/P2).

See also:
- Frontend screen inventory + known broken routes:
  `/Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/docs/frontend/FRONTEND_CURRENT_STATE.md`


## Scope and locked decisions for this phase

- **Auth pattern**: BFF proxy (Next.js Route Handlers + HttpOnly cookies).
- **Client V0 scope**: HRMS core only for “production-ready” requirements:
  Attendance/Leave/Workflow/DMS/Roster/Payroll.
  Non-core/legacy modules must be hidden behind permissions/feature flags.

Note: This phase is **hardening** and “no data leaks” work. It does not require
building all missing product screens yet, but it must make the UI safe and
operationally diagnosable.


## 1) Checklist vs Current State

Legend:
- Implemented: done end-to-end.
- Partial: present but incomplete or not enforced everywhere.
- Missing: not present.

| V0 checklist item | Status | Evidence (paths) | Notes |
| --- | --- | --- | --- |
| All API calls include correct scope headers | Implemented | `frontend/src/lib/api.ts`, `frontend/src/lib/selection.ts` | Scope headers are attached from persisted selection state on all wrapper calls. |
| Fail-closed scope errors redirect to scope selector with explanation + correlation id | Implemented | `frontend/src/lib/api.ts`, `frontend/src/app/scope/page.tsx` | Redirects to `/scope?reason=...&cid=...` on `iam.scope.*` codes. |
| Refresh rotation is race-safe (no multi-tab stampede) | Partial | `frontend/src/app/api/v1/[...path]/route.ts` | BFF refreshes on 401 once per request; concurrent refresh across tabs/instances can still stampede (see backlog). |
| Logout is reliable and revokes refresh token | Implemented | `frontend/src/components/shell/TopBar.tsx`, `frontend/src/app/api/v1/[...path]/route.ts` | Sign-out calls backend logout and clears cookies/state. |
| Errors show stable error code + correlation id | Implemented | `frontend/src/lib/api.ts`, `frontend/src/components/ErrorState.tsx` | Wrapper extracts `X-Correlation-Id` + envelope error fields. |
| Route-level error boundaries (App Router) exist | Implemented | `frontend/src/app/error.tsx`, `frontend/src/app/global-error.tsx`, `frontend/src/app/not-found.tsx` | Prevents “white screen” failures. |
| Permission gating (nav + actions) is driven by `/api/v1/auth/me` | Partial | `frontend/src/components/AuthBootstrap.tsx`, `frontend/src/config/navigation.ts`, `backend/app/auth/router.py` | Nav is gated; route-level guards and per-action gating are not complete. |
| Supportability: correlation IDs searchable in logs + shown to users | Implemented | `frontend/src/components/ErrorState.tsx`, `backend/app/core/middleware/trace.py` | Correlation id is shown in error UI and present in backend logs. |


## 2) Critical production blockers (P0)

### P0-A: Secrets committed to repository

Status:
- The file was removed from the working tree and `backend/secrets/` is now
  ignored by git (`.gitignore`).
- Docker compose no longer mounts a repo-local firebase key.
- `.env.docker` no longer contains real keys (placeholder values only).

Remaining required actions (still production-blocking):
1) Rotate the Firebase key in Google Cloud (out-of-band).
2) Remove the secret from git history (history rewrite), coordinated with your
   Git hosting and deployment pipelines.
3) Add guardrails (secret scanning in CI) to prevent re-commit.


## 3) Hardening Backlog (P0 / P1 / P2)

### Completed hardening (already implemented)

- BFF proxy for `/api/v1/*`: `frontend/src/app/api/v1/[...path]/route.ts`
- Backend auth responses include permissions: `backend/app/auth/router.py`
- Auth bootstrap via `/auth/me`: `frontend/src/components/AuthBootstrap.tsx`
- Permission-gated navigation + hiding placeholder modules: `frontend/src/config/navigation.ts`
- Correlation-aware error UX: `frontend/src/lib/api.ts`, `frontend/src/components/ErrorState.tsx`
- App Router error boundaries: `frontend/src/app/error.tsx`, `frontend/src/app/global-error.tsx`, `frontend/src/app/not-found.tsx`
- Scope remediation route: `frontend/src/app/scope/page.tsx`
- Logout calls backend revocation via BFF: `frontend/src/components/shell/TopBar.tsx`


### P0 — Remaining production blockers

1) **Secret hygiene guardrails**
   - Rotate Firebase keys (out-of-band).
   - Add secret scanning in CI (gitleaks or similar).
   - Coordinate git-history removal of previously committed secrets.

2) **Refresh stampede mitigation**
   - Add a per-session refresh lock in the BFF route handler so concurrent
     requests don’t cause refresh-token reuse and forced logout.

3) **Route-level gating**
   - Add Next.js middleware to:
     - redirect unauthenticated users to `/login` before mounting protected
       pages,
     - redirect scope-required users to `/scope` pre-emptively.


### P1 — Product stability improvements (recommended next)

1) Fix branch-scoping mismatches in legacy CCTV/job/report/calibration UI or hide
   those screens behind feature flags/permissions for Client V0.
   - Evidence and specific broken paths are listed in:
     `docs/frontend/FRONTEND_CURRENT_STATE.md`

2) Fonts consistency:
   - Either wire Geist via `next/font` in `frontend/src/app/layout.tsx`,
     or remove Geist CSS variable expectation.

3) “No selection” UX on scope-dependent screens:
   - Explicitly require a branch selection before loading branch-scoped pages.


### P2 — CI confidence and E2E verification

1) Add Playwright E2E smoke flows aligned with V0:
   - Login → `/auth/me` → scope selection → load one page per persona.
   - ESS: punch in/out + see today status.
   - Manager: approve in workflow inbox.
   - Payroll: generate → approve → publish → employee downloads payslip JSON.

2) Add a small frontend contract test ensuring:
   - backend envelope is stable for key endpoints
   - `X-Correlation-Id` is present on responses (through the BFF).
