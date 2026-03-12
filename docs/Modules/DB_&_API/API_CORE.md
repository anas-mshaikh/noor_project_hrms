# Enterprise API Core (v1)

This repo uses `/api/v1` only.

This document describes the enterprise API core running on DB vNext (`tenancy`, `iam`, `hr_core`, `workflow`, `dms`).

## Response envelope

Enterprise endpoints use a stable envelope:

- Success:
  - `{ "ok": true, "data": <payload>, "meta"?: {...} }`
- Error:
  - `{ "ok": false, "error": { "code": "...", "message": "...", "details"?: ..., "correlation_id"?: "..." } }`

## Correlation IDs + logs

- Every request gets a correlation id.
- Response header: `X-Correlation-Id`
- You can pass `X-Correlation-Id` (legacy `X-Trace-Id` is accepted as input during transition).

## Auth model (JWT + refresh token rotation)

Access tokens are short-lived JWTs (`Authorization: Bearer <token>`).

Refresh tokens are random secrets returned once to clients and stored only as hashes in Postgres (`iam.refresh_tokens`).

Hashing model:

- `token_hash = sha256(refresh_token + AUTH_REFRESH_TOKEN_PEPPER)`
- Raw refresh tokens are never stored.

Rotation model:

- `/auth/refresh` revokes the old refresh token and issues a new pair.
- `/auth/logout` revokes the provided refresh token.

### Endpoints

- `POST /api/v1/auth/login`
- `POST /api/v1/auth/refresh`
- `POST /api/v1/auth/logout`
- `GET  /api/v1/auth/me`

## Scope resolution (tenant/company/branch)

RBAC is based on `iam.user_roles` (scoped by `tenant_id` + optional `company_id`/`branch_id`).

Active scope is resolved from:

- access token (`sub = user_id`)
- user role assignments in DB
- optional headers:
  - `X-Tenant-Id`
  - `X-Company-Id`
  - `X-Branch-Id`

Tenant behavior:

- Single-tenant users default to their only tenant.
- Multi-tenant users must send `X-Tenant-Id` or receive `400` (`TENANT_REQUIRED`).

## Bootstrap (one-time)

`POST /api/v1/bootstrap`

Rules:

- Allowed only when `tenancy.tenants` is empty (fresh install).
- Creates tenant + company + branch + admin user + ADMIN role assignment.
- Returns access + refresh tokens (same shape as `/auth/login`).

Important:

- `backend/alembic/versions/aca6f7cb881b_db_vnext_0003_seed_demo_tenant.py` is opt-in (`DB_VNEXT_SEED_DEMO_TENANT=1`).
- For bootstrap-first setup, keep `DB_VNEXT_SEED_DEMO_TENANT` unset and reset DB volume.

Example:

```bash
docker compose down -v
docker compose up --build

curl -s -X POST http://localhost:8000/api/v1/bootstrap \
  -H 'content-type: application/json' \
  -d '{
    "tenant_name":"Acme",
    "company_name":"Acme LLC",
    "branch_name":"HQ",
    "branch_code":"HQ",
    "timezone":"Asia/Riyadh",
    "currency_code":"SAR",
    "admin_email":"admin@acme.test",
    "admin_password":"StrongPass123"
  }'
```

## Authorization model

Authorization is permission-driven via `require_permission(...)`, with permissions loaded from IAM role mappings and cached in Redis.

Examples of enforced permission codes:

- `tenancy:read`, `tenancy:write`
- `iam:user:read`, `iam:user:write`, `iam:role:assign`, `iam:permission:read`
- `hr:employee:read`, `hr:employee:write`, `hr:employment:write`
- `hr:team:read`, `ess:profile:read`, `ess:profile:write`
- `notifications:read`
- Vision/task/mobile/import permissions (branch-scoped APIs)

## Tenancy APIs

Routes:

- `GET/POST /api/v1/tenancy/companies`
- `GET/POST /api/v1/tenancy/branches`
- `GET/POST /api/v1/tenancy/org-units`
- `GET      /api/v1/tenancy/org-chart`
- `GET/POST /api/v1/tenancy/job-titles`
- `GET/POST /api/v1/tenancy/grades`

Authorization:

- Uses permissions (`tenancy:read`, `tenancy:write`).

## IAM APIs

### Users

- `POST   /api/v1/iam/users`
- `GET    /api/v1/iam/users?limit=&offset=&q=&status=`
- `GET    /api/v1/iam/users/{user_id}`
- `PATCH  /api/v1/iam/users/{user_id}`

Authorization:

- Permission-driven (`iam:user:read`, `iam:user:write`).

Notes:

- IAM is tenant-scoped: list/get/update operate inside active tenant.
- `POST /api/v1/iam/users` assigns a default employee role mapping in active scope.

### Role assignments

- `POST   /api/v1/iam/users/{user_id}/roles`
- `GET    /api/v1/iam/users/{user_id}/roles`
- `DELETE /api/v1/iam/users/{user_id}/roles?role_code=...&company_id=...&branch_id=...`

Role assignment scope model (`iam.user_roles`):

- `(tenant_id)` applies to all companies/branches in tenant.
- `(tenant_id, company_id)` applies to all branches under that company.
- `(tenant_id, company_id, branch_id)` applies to that branch only.

### Catalog

- `GET /api/v1/iam/roles`
- `GET /api/v1/iam/permissions`

## Scope header hardening

Headers:

- `X-Tenant-Id`
- `X-Company-Id`
- `X-Branch-Id`

These headers are validated against caller scope from `iam.user_roles` and cannot be spoofed.
If requested scope is not covered, API returns `403` (`iam.scope.forbidden`) with `correlation_id`.

## HR Core

DB vNext is the system of record for employee master data:

- `hr_core.persons`
- `hr_core.employees`
- `hr_core.employee_employment`
- `hr_core.employee_user_links`

### Employment history model

- Employment assignments are effective-dated rows (`start_date`, `end_date`).
- A row is current when `end_date IS NULL`.
- Current row selection is deterministic:
  - prefer `end_date IS NULL AND is_primary = TRUE`
  - fallback: `end_date IS NULL ORDER BY start_date DESC LIMIT 1`

### Manager hierarchy rules

- Manager is stored on current employment row (`manager_employee_id`).
- Manager assignments are validated cycle-free using recursive CTE over current manager chain.

### HR endpoints (`/api/v1/hr/*`)

Routes:

- `POST   /api/v1/hr/employees`
- `GET    /api/v1/hr/employees?q=&status=&branch_id=&org_unit_id=&limit=&offset=`
- `GET    /api/v1/hr/employees/{employee_id}`
- `PATCH  /api/v1/hr/employees/{employee_id}`
- `POST   /api/v1/hr/employees/{employee_id}/employment`
- `GET    /api/v1/hr/employees/{employee_id}/employment`
- `POST   /api/v1/hr/employees/{employee_id}/link-user`

Authorization:

- Permission-driven (`hr:employee:read`, `hr:employee:write`, `hr:employment:write`).

### ESS endpoints (`/api/v1/ess/*`)

Employee self-service requires IAM user linkage via `hr_core.employee_user_links`.
If not linked, API returns `409` with code `ess.not_linked`.

Routes:

- `GET   /api/v1/ess/me/profile`
- `PATCH /api/v1/ess/me/profile`

### MSS endpoints (`/api/v1/mss/*`)

Manager self-service requires:

- permission to read team scope (`hr:team:read`)
- employee linkage via `hr_core.employee_user_links`

Team computation rules:

- Uses current employment rows only (`end_date IS NULL`, primary preferred).
- Direct reports: `manager_employee_id = <actor_employee_id>`
- Indirect reports: recursive traversal of current manager graph.

Routes:

- `GET /api/v1/mss/team?depth=1|all&q=&status=&branch_id=&org_unit_id=&limit=&offset=`
- `GET /api/v1/mss/team/{employee_id}`

Field exposure:

- MSS does not return DOB, nationality, or address.

## Notifications (In-App, Milestone 1)

In-app notifications are supported via outbox consumption.

Worker pipeline:

- Producer table: `workflow.notification_outbox`
- Consumer: `backend/app/worker/notification_worker.py`
- Inbox table: `workflow.notifications`

Routes:

- `GET  /api/v1/notifications?unread_only=0|1&limit&cursor`
- `GET  /api/v1/notifications/unread-count`
- `POST /api/v1/notifications/{id}/read`
- `POST /api/v1/notifications/read-all`

Behavior:

- Always filtered by active tenant + recipient user.
- Permission required: `notifications:read`.

## Branch-first module APIs (legacy removed)

Legacy `/api/v1/stores*` and `/api/v1/organizations*` routes are removed.

Core branch-first patterns:

- `/api/v1/branches/{branch_id}/videos/...`
- `/api/v1/branches/{branch_id}/cameras...`
- `/api/v1/branches/{branch_id}/tasks...`
- `/api/v1/branches/{branch_id}/faces...`
- `/api/v1/branches/{branch_id}/months/{month_key}/...`
- HR recruiting routes are also branch-scoped.
