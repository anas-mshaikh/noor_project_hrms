# Backend Release Checklist

## Required checks
- `backend-ci.yml` green
- `backend-integration.yml` green
- `backend-nightly.yml` green when the release touches cross-domain flows

## Local release candidate drill
- `./scripts/backend-ci.sh`
- `./scripts/backend-integration.sh`
- `RUN_GOLDEN=1 ./scripts/backend-nightly.sh`

## Release review
- Verify Alembic head is applied cleanly from an empty database.
- Verify `/api/v1/health`, `/api/v1/healthz`, and `/api/v1/readyz`.
- Verify OpenAPI snapshot diff is intentional.
- Verify correlation IDs appear on representative success and error responses.
- Verify participant-safe paths do not leak DMS/payslip existence.

## Rollback
- Use the backend migration and deployment procedure in `docs/CI_CD/ROLLBACK.md`.
- If the issue is contract-only, revert the offending backend change and re-run `backend-integration.yml`.
