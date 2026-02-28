# M2 Platform Hardening (Web Frontend)

Last updated: 2026-02-27

This document captures the production-readiness hardening done in **Milestone 2** for the Noor HRMS **web** frontend (Next.js App Router). It focuses on debuggability (correlation IDs), consistent error handling, scope safety, downloads correctness, and React Query defaults.

Scope: `frontend/` only. No backend endpoints were added.


## 1) Correlation ID (End-to-End)

### What we do
- The API layer captures correlation IDs from:
  - Response header: `X-Correlation-Id` (preferred), or `X-Trace-Id` (fallback)
  - Error envelope: `error.correlation_id`
- Correlation IDs are surfaced to the user in:
  - DS ErrorState (with copy-to-clipboard)
  - Error toasts (with copy-to-clipboard)

### Key files
- API capture/normalization: `frontend/src/lib/api.ts`
- Error UI: `frontend/src/components/ds/ErrorState.tsx`
- Toast helper: `frontend/src/lib/toastApiError.ts`

### Debug workflow
1) User sees "Reference: <cid>" in UI
2) Use that value to search backend logs (backend logs include correlation_id)


## 2) Unified ApiError Contract

All API failures are normalized into `ApiError` so UI code can reliably render:

```ts
class ApiError extends Error {
  status: number;
  code: string;              // stable domain code or "unknown"
  correlationId: string|null;
  details: unknown|null;
  method: string|null;
  endpoint: string|null;
  isNetworkError: boolean;
}
```

### What’s covered
- `apiJson()` and `apiForm()` normalize:
  - Network failures -> `status=0`, `code="network_error"`, `isNetworkError=true`
  - Non-2xx -> parse JSON envelope error when present
- `xhrUploadFormWithProgress()` normalizes upload failures (XHR path) to `ApiError`

### Key file
- `frontend/src/lib/api.ts`


## 3) Error Code -> UX Mapping

We map stable backend error codes into friendly, actionable UX:
- Scope errors (`iam.scope.*`) suggest **Reset selection** / **Go to scope**
- 401 suggests **Sign in**
- Network/5xx suggests **Retry**

### Key file
- Mapping: `frontend/src/lib/errorUx.ts`

### How to add a new mapping
Add a case to `getErrorUx()` based on `ApiError.code` and/or `ApiError.status`.


## 4) Scope Hardening (Fail-Closed + Loop Breaker)

### Problem
Backend is fail-closed for multi-tenant scoping. If the browser stores a stale company/branch, *even `/auth/me` can fail*, causing users to get stuck.

### Solution (Client V0)
- Selection is stored in localStorage **and** mirrored into cookies:
  - `noor_scope_tenant_id`
  - `noor_scope_company_id`
  - `noor_scope_branch_id`
- The BFF proxy injects missing scope headers from these cookies for requests that cannot set headers (e.g. `<img>`, downloads, new tabs).
- When scope errors occur, we clear the invalid selection (and cookie mirror) before redirecting to `/scope`.

### Key files
- Selection storage + cookie mirror: `frontend/src/lib/selection.ts`
- Scope error loop-breaker: `frontend/src/lib/api.ts`
- BFF scope header injection: `frontend/src/app/api/v1/[...path]/route.ts`
- Scope remediation UI: `frontend/src/app/scope/page.tsx`

### Relevant backend error codes
- `iam.scope.tenant_required`
- `iam.scope.forbidden`
- `iam.scope.forbidden_tenant`
- `iam.scope.mismatch`
- `iam.scope.invalid_tenant`
- `iam.scope.invalid_company`
- `iam.scope.invalid_branch`


## 5) Downloads Pipeline (Raw Bytes + Envelope Errors)

### Requirements
Some endpoints return raw bytes on success (CSV, images, JSON files, etc.) but return JSON envelope errors on failure.

### Implementation
- `apiDownload()`:
  - does **not** JSON-parse on success (always treats response as bytes)
  - on failure (`!res.ok`) parses the envelope error when present and throws `ApiError`
  - extracts filename from `Content-Disposition` (`filename*` / `filename`) with fallback
- `saveBlobAsFile()` triggers a browser download.

### Key file
- `frontend/src/lib/api.ts`

### Adoption
- Report artifacts download now uses `apiDownload()` instead of `<a href>`:
  - `frontend/src/app/reports/[jobId]/page.tsx`


## 6) React Query Production Defaults

Defaults aim to avoid:
- infinite retry storms on 403/404/scope errors
- flicker from overly aggressive refetch

### Current defaults
- `refetchOnWindowFocus: false`
- `retry`: only for network errors / 5xx (bounded)
- `staleTime: 30s`
- `gcTime: 5m`
- `mutations.retry: false`

### Key file
- `frontend/src/app/providers.tsx`


## 7) Fixed Branch-Scoped Path Mismatches

The backend requires branch scoping for Vision/CCTV job/report flows. These paths are now consistent:
- UploadWizard job creation:
  - `frontend/src/components/UploadWizard.tsx`
- Job read/cancel/retry:
  - `frontend/src/app/jobs/[jobId]/page.tsx`
- Report queries + artifacts:
  - `frontend/src/app/reports/[jobId]/page.tsx`
- Camera calibration:
  - `frontend/src/app/cameras/[cameraId]/calibration/page.tsx`
- Event snapshot URLs:
  - `frontend/src/components/EventsTable.tsx`


## 8) Tests (Vitest)

Unit tests cover:
- correlation-id capture precedence (payload vs header)
- `apiDownload()` envelope error throwing
- content-disposition filename parsing
- scope UX mapping for key error codes

Key files:
- Config: `frontend/vitest.config.ts`
- Tests:
  - `frontend/src/lib/api.test.ts`
  - `frontend/src/lib/errorUx.test.ts`

Run:
```bash
cd frontend
npm run test
```


## 9) Quick Manual QA Checklist

- Correlation:
  - Trigger any API error -> ErrorState/toast shows Reference + copy works
- Scope recovery:
  - Force a stale branch/company -> app redirects to `/scope` and selection is cleared
- Downloads:
  - Download an artifact -> correct filename
  - 404 artifact -> shows friendly error, no garbage file downloaded
- Vision routes:
  - Upload video -> create job -> open report -> snapshot previews load
- React Query:
  - 403/404 responses should **not** retry repeatedly

