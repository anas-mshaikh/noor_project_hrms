# Backend Support Runbook

## Correlation IDs
- All HTTP responses should include `X-Correlation-Id`.
- Error envelopes should include `error.correlation_id`.
- Search backend logs for:
  - `correlation_id=<value>`

## Common checks
- Health:
  - `GET /api/v1/health`
  - `GET /api/v1/healthz`
  - `GET /api/v1/readyz`
- Authentication and scope:
  - `GET /api/v1/auth/me`
- OpenAPI contract:
  - compare `docs/openapi/backend.openapi.snapshot.json`

## Common failure classes
- `iam.scope.tenant_required`
  - multi-tenant user omitted `X-Tenant-Id`
- `iam.scope.invalid_company` / `iam.scope.invalid_branch`
  - malformed or unknown scope headers
- `iam.scope.mismatch`
  - header and path scope do not match
- `dms.document.not_found` / `payroll.payslip.not_found`
  - expected participant-safe behavior for inaccessible resources

## Local debugging
- Run fast backend checks:
  - `./scripts/backend-ci.sh`
- Run compose-backed backend integration:
  - `./scripts/backend-integration.sh`
- Dump compose logs:
  - `docker compose logs --no-color`
  - `docker compose --profile backend-ci logs --no-color`
