# Runbook: Mobile Login Bootstrap Mapping (`users/{uid}`)

This runbook documents how the backend provisions and maintains the Firestore mapping doc:

`users/{uid}`

This doc is used by the React Native app to bootstrap context:

Auth login → get `uid` → read `users/{uid}` → discover `tenant_id`, `branch_id`, `employee_code` → read month docs:

- `tenants/{tenantId}/branches/{branchId}/months/{YYYY-MM}/employees/{employee_code}`
- `tenants/{tenantId}/branches/{branchId}/months/{YYYY-MM}/leaderboards/*`

## Source of truth

- Postgres table: `mobile_accounts` (source of truth)
- Firestore doc: `users/{uid}` (derived cache)

## Required env vars (backend)

Auth + RBAC:
- Mobile endpoints require a valid JWT and the `mobile:accounts:*` permissions.

Firebase credentials (required unless dry-run):
- `FIREBASE_SERVICE_ACCOUNT_JSON_BASE64` (preferred) OR `FIREBASE_SERVICE_ACCOUNT_PATH`
- Optional: `FIREBASE_PROJECT_ID`

Dry-run (recommended for first local wiring):
- `MOBILE_MAPPING_DRY_RUN=true` (no Firebase calls; logs payload only)

## Provision an employee (email/password MVP)

Endpoint:
- `POST /api/v1/branches/{branch_id}/employees/{employee_id}/mobile/provision`

Body:
```json
{ "email": "employee@example.com", "role": "employee" }
```

Notes:
- If you omit `temp_password`, the backend will generate a temporary password and return it as `generated_password`.
- If you call provision again for the same `(branch_id, employee_id)`, it is idempotent: it reuses the existing mapping.

Expected result:
- Postgres row in `mobile_accounts`
- Firestore doc `users/{firebase_uid}` with:
  `tenant_id`, `branch_id`, `employee_id`, `employee_code`, `department`, `role`, `active`, `created_at`, `revoked_at`

## Verify Firestore doc

In Firestore console:
- Find `users/{uid}`
- Confirm `active == true` and IDs match your Postgres row.

## Revoke access

Endpoint:
- `POST /api/v1/branches/{branch_id}/employees/{employee_id}/mobile/revoke`

Expected result:
- Postgres: `mobile_accounts.active=false`, `revoked_at` set
- Firebase Auth user is disabled
- Firestore: `users/{uid}` updated with `active=false` and `revoked_at`

## Re-sync mapping doc

Endpoint:
- `POST /api/v1/mobile/resync/{firebase_uid}`

Use this if:
- Firestore doc was deleted manually
- You changed an employee’s `employee_code` and need to push the updated value

## Security rules (note)

You should set Firestore rules so the mobile client can:
- Read `users/{uid}` only for their own `uid`
- Read branch month docs only if:
  - `users/{uid}.active == true`
  - and the path tenant/branch matches the mapping
