# API Conventions

## Envelope contract

JSON endpoints follow the stable envelope contract:
- success: `{ "ok": true, "data": ... }`
- failure: `{ "ok": false, "error": { "code": "...", "message": "...", "details": ..., "correlation_id": "..." } }`

## Downloads

Raw download endpoints return bytes on success. On failure they still follow standardized backend error handling and return the correlation ID header.

## Versioning and paths

- Primary API prefix: `/api/v1`
- Domain routers generally keep module-specific prefixes (`/leave`, `/workflow`, `/payroll`, `/dms`, etc.) under `/api/v1`
- Scope-sensitive endpoints must enforce tenant and branch/company boundaries server-side

## Auth and scope headers

- Multi-tenant requests may require `X-Tenant-Id`
- Responses surface `X-Correlation-Id`
- Frontend route guards and backend authorization are separate concerns; backend remains authoritative

## Contract references

- OpenAPI snapshot: `docs/backend/openapi/backend.openapi.snapshot.json`
- Shared error and response logic: `backend/app/core/errors.py`, `backend/app/core/responses.py`
