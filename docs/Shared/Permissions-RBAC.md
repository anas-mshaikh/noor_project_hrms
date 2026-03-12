# Permissions and RBAC

## Platform conventions

- Permission codes use colon-style naming such as `leave:request:submit` or `payroll:payrun:generate`.
- Frontend gating is a UX convenience only. Backend authorization remains the source of truth.
- Route-level and action-level permission checks should both fail closed.

## Common patterns

- Module routers expose lightweight policy helpers (for example, `require_leave_request_submit`).
- Settings pages and admin consoles normally require both read and write distinctions.
- ESS and MSS surfaces should rely on participant-safe reads where appropriate.

## Documentation rule

Module docs should list module-specific permissions, but this shared document defines the platform naming and enforcement conventions.

See also:
- `docs/CI_CD/RBAC_MATRIX.md`
- `backend/app/auth/permissions.py`
- `backend/app/auth/deps.py`
