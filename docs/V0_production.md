# Production-ready plan for Noor HRMS Client V0

## Product scope and production-readiness goals

This plan is for shipping **Client V0** of the Noor Attendance + HRMS suite to production by making the **existing** system complete, consistent, and end-to-end usable on **real backend data**, without inventing new modules, endpoints, or workflows. The backend is already organised around enterprise-grade foundations (multi-tenancy, IAM, HR core, workflow, DMS) and domain modules (attendance, leave, roster, payable summaries, payroll, onboarding, profile change), all under `/api/v1`. fileciteturn0file0 fileciteturn0file3

The practical definition of “production-ready” for Client V0 is:

- **Deterministic access + session behaviour**: login → refresh → logout works and survives reloads; `/api/v1/auth/me` always produces the identity + permission picture the UI will enforce. fileciteturn0file0  
- **Hard-correct scoping**: tenant/company/branch selection is explicit, persists, and **every request** uses the correct scope headers; scope spoofing is not possible and must be treated as a first-class user experience (clear “why you can’t access” messaging). fileciteturn0file0  
- **Operational clarity**: envelope/unwrapping, stable error banners, and correlation IDs are surfaced so support can diagnose issues quickly. fileciteturn0file0  
- **Role safety**: navigation, screens, and actions are permission-gated, aligning to backend `require_permission(...)` enforcement (no “UI-only security”). fileciteturn0file0  
- **Client-operable workflows** (within existing backend capabilities): the HR team can set up core masters, onboard employees, run day-to-day attendance + leave + approvals, and complete a payroll cycle using the current APIs and workflow hooks. fileciteturn0file0 fileciteturn0file5 fileciteturn0file7 fileciteturn0file8  

Where “best in the market” is interpreted for V0 as: **low-friction self-service, fast approvals, consistent information architecture, and high trust** (auditability, good errors, predictable rules). Industry guidance consistently highlights HR tech value coming from efficiency in core functions (payroll, attendance, onboarding), improved employee experience via self-service, and compliance/risk controls. citeturn4search2

## Access, scoping, and error-handling architecture

### Backend contract that the frontend must treat as non-negotiable

Most enterprise endpoints return an envelope:

- Success: `{ ok: true, data: ... }`
- Error: `{ ok: false, error: { code, message, details?, correlation_id? } }`

Correlation IDs are emitted in `X-Correlation-Id` and may also appear in error payloads; Client V0 must capture them and display them in error banners/toasts. fileciteturn0file0

Some **legacy-style** endpoints (notably around Vision/Face) may not follow the envelope convention; Client V0 must not assume “every response is enveloped” globally, even if V0 mostly uses enveloped HRMS endpoints. fileciteturn0file2

### Authentication flows and token lifecycle

The backend uses short-lived JWT access tokens plus refresh token rotation:

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh` (revokes old refresh token, issues a new pair)
- `POST /api/v1/auth/logout` (revokes provided refresh token)
- `GET /api/v1/auth/me` (identity + permissions baseline) fileciteturn0file0

From a production-hardening standpoint, the key risks to manage are: token leakage, refresh race conditions, and “ghost sessions” in shared devices.

Security guidance for browser sessions emphasises: prefer **secure cookie properties** (HTTPS-only, HttpOnly) and clear session termination behaviour; cookies should use restrictive scope and appropriate SameSite settings. citeturn0search3 The same body of guidance also notes that bearer tokens used as session secrets should not be treated as permanently persistent. citeturn0search3

Separately, entity["organization","OWASP","web security nonprofit"] guidance highlights that **sensitive data (including session identifiers)** should not be stored in local storage because it is accessible to JavaScript and vulnerable to XSS exfiltration; HttpOnly cookies mitigate that exposure. citeturn1search0

A production-ready Client V0 should therefore implement one of these two **supported** patterns (both respect the existing backend APIs; neither requires backend feature changes):

- **BFF (recommended for enterprise web)**: Next.js Route Handlers proxy backend calls; refresh token stored HttpOnly; server attaches `Authorization: Bearer` when calling the backend; client never sees refresh token. This aligns with cookie hardening guidance and reduces token exposure surface. citeturn0search3turn1search0  
- **Direct-to-backend (acceptable if time-constrained)**: access token in memory + refresh token in HttpOnly cookie, with a guarded “bootstrap refresh” on app load to obtain a fresh access token before fetching `/auth/me`. This still requires strict error handling around refresh rotation to avoid multi-tab refresh stampedes. citeturn0search3turn1search4

Refresh token rotation is explicitly described as a best practice to reduce replay windows and detect breach by invalid-token reuse; standards guidance also explains that rotation should revoke the active chain if reuse is detected. entity["organization","Internet Engineering Task Force","internet standards org"] documentation describes refresh token rotation semantics and the “compromised token used by attacker + legitimate client” detection/revocation behaviour. citeturn1search4turn1search10

### Tenant/company/branch scope handling

The backend resolves active scope from the access token identity plus role assignments and scope headers:

- `X-Tenant-Id`, `X-Company-Id`, `X-Branch-Id`

Multi-tenant users must send `X-Tenant-Id` (otherwise `400 TENANT_REQUIRED`), and headers are validated against `iam.user_roles` so they cannot be spoofed; invalid scope returns a `403 iam.scope.forbidden` error code with correlation ID. fileciteturn0file0

Client V0 must therefore implement a **first-class Scope Selector**:

- Stores selected tenant/company/branch in a persistent store (these IDs are not secrets, but they are still operationally sensitive; they should not be logged into third-party analytics without a clear data policy).  
- Blocks navigation into scope-dependent areas until scope is valid.
- On any `TENANT_REQUIRED` or `iam.scope.forbidden` response, redirects the user to scope selection with a clear “what happened” explanation and the correlation ID for support. fileciteturn0file0

### Error boundaries, observability, and correlation-ready UX

Client V0 should treat error handling as part of “market-leading trust”:

- Use Next.js App Router conventions (`error.tsx` segment boundaries + a `global-error.tsx`) so one failing module doesn’t crash the shell. Next.js also strips sensitive server error details in production, emphasising the need to log/correlate errors server-side rather than relying on client-rendered stack traces. citeturn0search0turn0search2  
- Implement “expected error” handling (validation errors, 409 conflicts, RBAC denies) as explicit UI outcomes (inline form errors, banners, and conflict-resolution messages), not as generic crash screens. citeturn0search2  
- Capture and surface correlation IDs consistently. Correlation IDs are also a common concept in distributed tracing; standards bodies note the privacy risk of propagating identifiers and recommend not embedding PII in trace headers. entity["organization","World Wide Web Consortium","web standards body"] guidance on trace context privacy is a useful constraint: correlation/trace identifiers must not carry sensitive user data. citeturn2search9  

Finally, production readiness requires that security-relevant events be logged coherently. entity["organization","OWASP","web security nonprofit"] logging guidance highlights authentication successes/failures, authorisation failures, and validation failures as events that should be logged and monitored. citeturn2search3 In Client V0 terms: always show correlation IDs and stable error codes so backend logs can be searched reliably. fileciteturn0file0

## Role model and client-facing UX principles

### Roles as clients experience them

A competitive HRMS is judged less by the number of modules and more by whether each persona can get their job done quickly and safely:

- **Employee (ESS)**: wants “my day” clarity (attendance status, leave balance, payslips, onboarding tasks) with minimal HR dependency. Research and professional guidance commonly link HR tech value to employee experience via self-service and reduced friction. citeturn4search2turn4search0  
- **Manager (MSS approver)**: wants a clean inbox, fast decision-making, and team visibility (leave calendar, payable summaries). fileciteturn0file5 fileciteturn0file7  
- **HR Admin**: wants authoritative masters (employee records, employment, documents, leave policies, rosters) and auditability. fileciteturn0file0 fileciteturn0file4 fileciteturn0file5 fileciteturn0file10  
- **Payroll Admin**: wants deterministic generation, approvals, publishing, and employee self-access to payslips. fileciteturn0file8  
- **Tenant/Admin (IT or HRIS owner)**: wants tenancy + IAM configuration and safe role assignment. fileciteturn0file0  

### Permission-driven UX and least privilege

Backend authorisation is permission-driven (colon-style permissions, enforced via `require_permission(...)`), so the UI must be permission-driven as well: hide navigation that the user can’t access, and protect routes server-side so deep links don’t leak data. fileciteturn0file0

This aligns directly with the principle of least privilege: only expose the minimum capabilities required for the user’s job. entity["organization","OWASP","web security nonprofit"] access control guidance frames least privilege as reducing exploit impact by limiting permissions attached to code and users. citeturn2search8

### Navigation strategy for Client V0

To keep the system “complete and end-to-end usable” without new features, Client V0 should implement a simple, consistent navigation model:

- **Global**: Dashboard, Approvals, Notifications, Scope Switcher, Profile.
- **Employee**: Attendance, Leave, Onboarding, Documents, Payslips, Profile Changes.
- **Manager**: Team (directory + payable days), Team Leave Calendar.
- **HR Admin**: Employees, Leave Admin, Roster, Attendance Admin, Documents Admin.
- **Admin**: Tenancy, IAM.
- **Payroll**: Payroll Setup, Payruns.

Every navigation item should map to at least one existing endpoint and a permission set from the backend docs. fileciteturn0file0

## Screen and flow blueprint by module

The catalogue below is intentionally constrained to endpoints already described in the backend docs and is designed to be implementable with the existing Next.js shell and basic table/form UI patterns. It is derived from the API core docs and the domain module specifications. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2 fileciteturn0file4 fileciteturn0file5 fileciteturn0file6 fileciteturn0file7 fileciteturn0file8 fileciteturn0file9 fileciteturn0file10

| Navigation group | Screen (Client V0) | Primary roles | Required permissions (examples) | Key endpoints (existing) | V0-specific “must handle” rules |
|---|---|---|---|---|---|
| Access | Sign in / session bootstrap | All | — | `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`, `GET /auth/me` | Refresh rotation; show correlation ID on failures. fileciteturn0file0 |
| Access | Scope selector (tenant/company/branch) | All | — (driven by `/auth/me`) | All requests require `X-Tenant-Id` for multi-tenant; use scope headers on all calls | Handle `TENANT_REQUIRED` and `iam.scope.forbidden` as “scope action required”. fileciteturn0file0 |
| Global | Notifications | All | `notifications:read` | `GET /notifications?…`, `POST /notifications/{id}/read`, `POST /notifications/read-all` | Cursor pagination and unread-only filtering; surface correlation ID on errors. fileciteturn0file0 |
| Global | Approvals inbox | Manager / HR approver / payroll approver | `workflow:request:approve` (and domain read permissions) | `GET /workflow/inbox`, `POST /workflow/requests/{request_id}/approve`, `POST /workflow/requests/{request_id}/reject` | Retry-safe UX for `already decided`/conflict errors; show evidence attachments via domain data where available. fileciteturn0file2 fileciteturn0file5 |
| ESS | My profile | Employee | `ess:profile:read`, `ess:profile:write` | `GET /ess/me/profile`, `PATCH /ess/me/profile` | This is the “truth view” for employees; keep edits minimal and validated. fileciteturn0file0 |
| ESS | Attendance: Punch | Employee | `attendance:punch:read`, `attendance:punch:submit` | `GET /attendance/me/punch-state`, `POST /attendance/me/punch-in`, `POST /attendance/me/punch-out` | Branch timezone business day; conflict errors (already in/not in/leave conflict). fileciteturn0file1 |
| ESS | Attendance: Days calendar | Employee | `attendance:correction:read` (and/or punch read) | `GET /attendance/me/days?from&to` | Must display effective status with override precedence. fileciteturn0file1 fileciteturn0file2 |
| ESS | Attendance: Regularisation | Employee | `attendance:correction:submit`, `attendance:correction:read` | `POST /attendance/me/corrections`, `GET /attendance/me/corrections?…`, `POST /attendance/me/corrections/{id}/cancel` | Strict business rules: day window, leave conflict, idempotency behaviour, participant-only semantics. fileciteturn0file2 |
| ESS | Leave | Employee | `leave:request:submit`, `leave:request:read`, `leave:balance:read` | `GET /leave/me/balances`, `GET /leave/me/requests`, `POST /leave/me/requests`, `POST /leave/me/requests/{id}/cancel` | Leave approval writes attendance overrides; show workflow status clearly. fileciteturn0file5 |
| MSS | Team directory | Manager | `hr:team:read` | `GET /mss/team?…`, `GET /mss/team/{employee_id}` | Must support depth=1 vs all; branch/org filters; stable pagination. fileciteturn0file0 |
| MSS | Team leave calendar | Manager | `leave:team:read` | `GET /leave/team/calendar?from&to&depth&branch_id=…` | Calendar view is branch/timezone aware and is a core manager preference. fileciteturn0file5 |
| MSS | Team payable days | Manager | `attendance:payable:team:read` | `GET /attendance/team/payable-days?from&to&depth=…` | Used to answer “who is payable / absent”; depends on roster + overrides. fileciteturn0file7 |
| HR Admin | Employees directory + detail | HR | `hr:employee:read`, `hr:employee:write` | `GET /hr/employees?…`, `GET /hr/employees/{id}`, `POST /hr/employees`, `PATCH /hr/employees/{id}` | Must be “system of record” view; no mock HR data; deterministic filters. fileciteturn0file0 |
| HR Admin | Employment management | HR | `hr:employment:write` | `GET /hr/employees/{id}/employment`, `POST /hr/employees/{id}/employment` | Effective-dated employment rows; manager hierarchy correctness matters. fileciteturn0file0 |
| HR Admin | Link user to employee | HR / admin | `hr:employee:write` + IAM read | `POST /hr/employees/{id}/link-user` | Required for workflow participation and ESS identity mapping. fileciteturn0file0 fileciteturn0file8 |
| HR Admin | Attendance admin: punch settings | HR / time office | `attendance:settings:write` | `GET /attendance/punch-settings?branch_id=…`, `PUT /attendance/punch-settings?branch_id=…` | Must configure per branch; reflect defaults safely. fileciteturn0file1 |
| HR Admin | Attendance admin: corrections reporting | HR | `attendance:admin:read` | `GET /attendance/corrections?…` | Reporting is tenant-scoped; show correlation ID on errors; support cursor pagination. fileciteturn0file2 |
| HR Admin | Roster: shifts & defaults | HR / ops | `roster:shift:read`, `roster:shift:write`, `roster:defaults:write` | `POST /roster/branches/{branch_id}/shifts`, `GET /roster/branches/{branch_id}/shifts`, `PATCH /roster/shifts/{id}`, `GET/PUT /roster/branches/{branch_id}/default-shift` | Overnight shift support; expected minutes logic impacts payroll. fileciteturn0file10 fileciteturn0file7 |
| HR Admin | Roster: assignments & overrides | HR / ops | `roster:assignment:*`, `roster:override:*` | `POST /roster/employees/{employee_id}/assignments`, `GET /roster/employees/{employee_id}/assignments`, `PUT /roster/employees/{employee_id}/overrides/{day}`, `GET /roster/employees/{employee_id}/overrides?from&to` | Overlap validation and deterministic schedule resolution. fileciteturn0file10 |
| Leave Admin | Leave types, policies, allocations | HR | `leave:type:*`, `leave:policy:*`, `leave:allocation:write`, `leave:admin:read` | `GET/POST /leave/types`, `GET/POST /leave/policies`, `POST /leave/policies/{id}/rules`, `POST /leave/employees/{id}/policy`, `POST /leave/allocations` | Submissions depend on policies + workflow definition being active. fileciteturn0file5 |
| Leave Admin | Branch calendar config | HR / ops | leave admin perms | `GET/PUT /leave/calendar/weekly-off?branch_id=…`, `GET/POST /leave/calendar/holidays?...` | Weekly-off must be configured; downstream payable summaries fail closed without it. fileciteturn0file5 fileciteturn0file7 |
| Documents | Document types + employee docs | HR / verifier | `dms:*` perms | `GET/POST/PATCH /dms/document-types`, `POST /hr/employees/{id}/documents`, `GET /hr/employees/{id}/documents`, `POST /dms/documents/{id}/versions`, `POST /dms/documents/{id}/verify-request` | Participant-only 404 semantics; workflow-backed verification; local storage download flows. fileciteturn0file4 |
| ESS | My documents | Employee | `dms:document:read`, `dms:file:read` | `GET /ess/me/documents?…`, `GET /ess/me/documents/{id}` | Must never leak others’ docs; 404 on deny is expected. fileciteturn0file4 |
| Onboarding | Templates + bundles | HR | `onboarding:template:*`, `onboarding:bundle:*` | `GET/POST /onboarding/plan-templates`, `POST /onboarding/plan-templates/{id}/tasks`, `POST /onboarding/employees/{employee_id}/bundle`, `GET /onboarding/employees/{employee_id}/bundle` | Task snapshot at bundle creation; document tasks integrate with DMS + workflow. fileciteturn0file6 |
| Onboarding | My onboarding tasks | Employee | `onboarding:task:*` | `GET /ess/me/onboarding`, task submission endpoints | Document tasks upload and may create verification requests; consistent status UX is key. fileciteturn0file6 |
| Profile change | My requests + HR list | Employee / HR | `hr:profile-change:*` | ESS: `POST/GET/cancel /ess/me/profile-change-requests…`; HR list: `GET /hr/profile-change-requests…` | Approval applies change-set in workflow transaction; show replace semantics clearly. fileciteturn0file9 |
| Payable summaries | ESS/team/admin views + recompute | Employee / manager / HR | `attendance:payable:*` | `GET /attendance/me/payable-days`, `GET /attendance/team/payable-days`, `GET /attendance/admin/payable-days`, `POST /attendance/payable/recompute` | Hard dependency on weekly-off + roster + overrides; fail-closed calendar errors. fileciteturn0file7 |
| Payroll | Setup + compensation | Payroll admin | `payroll:*` setup perms | `POST/GET /payroll/calendars`, `POST/GET /payroll/calendars/{id}/periods`, `POST/GET /payroll/components`, `POST/GET /payroll/salary-structures`, `POST /payroll/salary-structures/{id}/lines`, `POST/GET /payroll/employees/{id}/compensation` | Deterministic configuration; no hidden calculations; currency/timezone fixed per calendar. fileciteturn0file8 |
| Payroll | Payrun lifecycle + payslips | Payroll admin / employee | `payroll:payrun:*`, `payroll:payslip:read` | `POST /payroll/payruns/generate`, `GET /payroll/payruns/{id}?include_lines=…`, `POST /payroll/payruns/{id}/submit-approval`, `POST /payroll/payruns/{id}/publish`, `GET /payroll/payruns/{id}/export?format=csv`, ESS payslip endpoints | Workflow-driven approval; payslips stored as DMS JSON documents; employee reads are participant-only. fileciteturn0file8 fileciteturn0file4 |
| Admin | Tenancy masters | Tenant/admin | `tenancy:read`, `tenancy:write` | `GET/POST /tenancy/companies`, `/tenancy/branches`, `/tenancy/org-units`, `/tenancy/job-titles`, `/tenancy/grades`, `GET /tenancy/org-chart` | Org structure must exist before HR + roster assignment feels usable. fileciteturn0file0 |
| Admin | IAM users + roles | Tenant/admin | `iam:user:*`, `iam:role:assign`, `iam:permission:read` | `/iam/users…`, `/iam/roles`, `/iam/permissions`, role assignment endpoints | Role assignment scoping model must be visible (tenant/company/branch). fileciteturn0file0 |

### Role-centric flows clients will actually follow

**Employee (ESS) “daily use” flow**  
Login → scope resolved (often default if single-tenant) → Dashboard → Punch in/out → Check attendance day status → submit regularisation only when needed → request leave → view notifications → view payslip when published. This is backed by punching endpoints and the override precedence model (leave overrides win; then correction overrides; then base attendance). fileciteturn0file1 fileciteturn0file2 fileciteturn0file5

Key UX expectations to meet:
- “Today” must use **branch timezone business day**, not the browser’s local date, because payroll and attendance are computed on branch timezone. fileciteturn0file1  
- Conflicts must be explained as business rules (e.g., punch blocked because the day is already on leave). fileciteturn0file1 fileciteturn0file2

**Manager (MSS) “approval + team awareness” flow**  
Login → Inbox → open request context (leave/correction/document/profile-change/payrun) → approve or reject → review team leave calendar and/or payable days to manage staffing. Workflow submissions and approvals are the central manager loop in this backend design. fileciteturn0file5 fileciteturn0file2 fileciteturn0file8

**HR Admin “operate the system” flow**  
Login → ensure org + employees exist → manage employment assignments and manager hierarchy → configure leave policies + calendars → configure roster and punch settings → support document verification and employee document library → respond to escalations (corrections, missing data) using correlation IDs. The HR core is explicitly the system of record for employee identity/employment, and DMS/workflow are structured to be auditable and safe. fileciteturn0file0 fileciteturn0file4

**Payroll Admin “monthly close” flow**  
Ensure prerequisites (leave calendar weekly-off, roster schedule, payable summaries) → configure payroll setup (calendar/periods/components/structures/compensation) → generate payrun → submit for approval → publish payslips (JSON stored in DMS) → employees view payslips via ESS endpoints. Payroll explicitly depends on payable summaries for proration inputs and publishes payslips via DMS documents. fileciteturn0file7 fileciteturn0file8 fileciteturn0file4

## Client operations playbook

This is the client-facing “how we operate Noor” runbook for V0. It is written in the order clients prefer: **setup once**, then **repeatable daily operations**, then **monthly payroll close**, with explicit prerequisites and failure modes.

### Implementation day fundamentals

If this is a fresh environment, backend supports a one-time `POST /api/v1/bootstrap` that creates tenant/company/branch/admin and returns tokens; it is only allowed when the tenants table is empty. fileciteturn0file0 This is operationally useful for customer pilots or a greenfield client where you need a controlled “first admin” flow.

After the first login, the client invariably wants three “Settings” areas ready before they onboard any employees:

- **Organisation structure (Tenancy)**: companies, branches, org units, job titles, grades, plus org chart. fileciteturn0file0  
- **User access (IAM)**: create users, understand role catalogue and permission catalogue, assign roles with correct scope granularity (tenant-wide vs company vs branch). fileciteturn0file0  
- **Employee record foundation (HR core)**: create employees, set employment assignment, set manager, and link employee ↔ user so ESS and workflow participation work correctly. fileciteturn0file0  

### HR readiness prerequisites that prevent “it doesn’t work” complaints

Clients will judge the system harshly if core modules fail because configuration steps were hidden. Client V0 should make these prerequisites explicit:

- **Leave requires branch calendar config** (weekly off + holidays) and policies; leave approval writes `attendance.day_overrides` as `ON_LEAVE`, which affects attendance status and payable computations. fileciteturn0file5  
- **Payable summaries fail closed** if weekly-off is not configured properly (must exist for weekdays 0..6 per branch in the backend design). That failure mode must be shown as an actionable configuration error, not a cryptic 400. fileciteturn0file7  
- **Onboarding document tasks rely on DMS and (optionally) workflow verification**, and onboarding “submit packet” creates an HR Profile Change request via workflow. If workflow definitions for those request types aren’t active, submissions will fail and must surface actionable messaging. fileciteturn0file6 fileciteturn0file9  
- **Payroll approvals and payrun publishing** are workflow-driven; publishing produces payslips as DMS JSON documents and notifies employees. The backend also notes that payroll admins must be linked to an employee record for workflow engine requirements, so you must operationally ensure those links exist for approvers. fileciteturn0file8  

### Daily operations the client will repeat

Clients tend to operate HRMS in predictable daily loops:

- **Employees**: punch, correct anomalies, request leave, upload onboarding documents, view notifications. All punching and day status must align to branch timezone and deterministic override precedence. fileciteturn0file1 fileciteturn0file2  
- **Managers**: clear inbox (approve/reject), check team calendar. fileciteturn0file5  
- **HR**: maintain rosters (shift templates, defaults, assignments, overrides), maintain leave policy assignments and allocations, support document verification and expiry rules. fileciteturn0file10 fileciteturn0file5 fileciteturn0file4  

### Compliance and privacy stance for client confidence

Even when V0 does not include advanced compliance tooling, the HR domain is inherently personal-data heavy. A client-ready HRMS should be delivered with a clear data-handling posture:

- Data minimisation, integrity/confidentiality, and accountability are core principles of GDPR-style privacy governance; they translate directly into: least-privilege access, tight audit trails, and limiting unnecessary data exposure in UI/logs. citeturn2search5turn2search8  
- Correlation IDs and tracing headers must not embed PII; they should remain opaque identifiers used purely for troubleshooting. citeturn2search9turn0file0  

## Release verification and go-live readiness

### Test strategy aligned to enterprise risk

The backend testing guidelines already define an enterprise “test pyramid” with unit/integration/api/contract/e2e layering, and explicitly call out tenant isolation, RBAC negative tests, idempotency behaviour, and concurrency safety as mandatory for mutating endpoints. fileciteturn0file12

Client V0 should mirror this with a small but high-value set of E2E flows (because the definition of done is end-to-end usability):

- Login → `/auth/me` → scope select → load at least one screen per persona.
- ESS: punch in/out + see today status.
- ESS: submit correction → manager approves in inbox → day status reflects override.
- ESS: submit leave → manager approves → attendance shows `ON_LEAVE`.
- Payroll: generate payrun → submit approval → approve → publish → employee retrieves payslip. fileciteturn0file0 fileciteturn0file1 fileciteturn0file2 fileciteturn0file5 fileciteturn0file8

### Production “hardening checklist” for the web app

Client V0 is ready to deploy when the following are demonstrably true:

- **All API calls** include correct `X-Tenant-Id` (and company/branch where applicable) and handle fail-closed behaviours (`TENANT_REQUIRED`, `iam.scope.forbidden`) with user-actionable UI. fileciteturn0file0  
- Token refresh is race-safe and respects rotation semantics; session termination is accessible and reliable. fileciteturn0file0 citeturn1search4turn0search3  
- Every error surfaced to users includes: a stable message, the backend error code when present, and correlation ID for support. fileciteturn0file0  
- Route-level error boundaries exist so module failures don’t crash the entire app; server errors are not assumed to contain sensitive details in production. citeturn0search0turn0search2  
- Permission-gating is enforced in routing and navigation based on `/auth/me` derived permissions (not hardcoded role names). fileciteturn0file0  
- Supportability is in place: correlation IDs are searchable in logs, and security-relevant events (auth failures, authorisation failures) are logged/monitored. citeturn2search3turn0file0  

If the goal is to be “best in the market” under a strict feature freeze, the decisive differentiator is that the system behaves predictably under real organisational complexity (multi-tenant scope, branch timezones, approvals, and auditability) while still feeling simple to employees and managers. That is achieved by executing the flows above with zero mock data, strict scope correctness, and relentless clarity in error handling and operational prerequisites. fileciteturn0file0 fileciteturn0file1 fileciteturn0file7 citeturn4search2