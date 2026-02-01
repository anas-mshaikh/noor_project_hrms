# Enterprise API Core (v1)

This repo uses **/api/v1** only.

This document describes the enterprise API core added on top of DB vNext (`tenancy`, `iam`, `hr_core`, `workflow`, `dms`).

## Response envelope

New enterprise endpoints return a stable envelope:

- Success:
  - `{ "ok": true, "data": <payload>, "meta"?: {...} }`
- Error:
  - `{ "ok": false, "error": { "code": "...", "message": "...", "details"?: ..., "trace_id"?: "..." } }`

## Trace IDs + logs

- Every request gets a trace id.
- Response header: `X-Trace-Id`
- You can pass your own `X-Trace-Id` and it will be echoed back.

## Auth model (JWT + refresh token rotation)

Access tokens are short-lived JWTs (`Authorization: Bearer <token>`).

Refresh tokens are **random secrets** returned once to clients and stored **only as hashes** in Postgres (`iam.refresh_tokens`).

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
- the access token (`sub = user_id`)
- user role assignments in DB
- optional headers:
  - `X-Company-Id`
  - `X-Branch-Id`

If headers are not provided, the API picks the first allowed scope (deterministic ordering).

## Bootstrap (one-time)

`POST /api/v1/bootstrap`

Rules:
- Allowed only when `tenancy.tenants` is empty (fresh install).
- Creates tenant + company + branch + admin user + ADMIN role assignment.
- Returns access + refresh tokens (same shape as `/auth/login`).

Important:
- `backend/alembic/versions/aca6f7cb881b_db_vnext_0003_seed_demo_tenant.py` is now **opt-in** (env var: `DB_VNEXT_SEED_DEMO_TENANT=1`).
- For a bootstrap-based setup, keep `DB_VNEXT_SEED_DEMO_TENANT` **unset** and reset the DB volume.

Example (Docker):

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

## Tenancy APIs

All tenancy CRUD endpoints require one of:
- `ADMIN`, `HR_ADMIN`, `HR_MANAGER`

Routes:
- `GET/POST /api/v1/tenancy/companies`
- `GET/POST /api/v1/tenancy/branches`
- `GET/POST /api/v1/tenancy/org-units`
- `GET      /api/v1/tenancy/org-chart`
- `GET/POST /api/v1/tenancy/job-titles`
- `GET/POST /api/v1/tenancy/grades`

Org chart ordering is deterministic (sorted by name).

