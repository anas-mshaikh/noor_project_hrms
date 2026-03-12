# Noor HRMS

Noor HRMS is a multi-tenant HR and operations platform built around a FastAPI backend, a Next.js web application, background workers, and a shared workflow engine. The current platform covers HR core, workflow approvals, attendance and leave, employee documents, roster and payables, payroll, IAM, tenancy, and ESS surfaces.

## What is in this system

- HR Core and Employee 360: employee directory, profiles, employment context, linked-user flows, onboarding, and profile change requests.
- Workflow backbone: request definitions, approvals, inbox and outbox, notifications, attachments, and terminal side effects across modules.
- Attendance and Leave: attendance days, punch flows, corrections, leave requests, leave approvals, and team calendar views.
- DMS: employee-scoped document library, document types, document verification workflows, expiry tracking, and ESS self-service document access.
- Roster and Payables: shift templates, branch defaults, employee assignments, date overrides, and payable-day views for employee, team, and admin.
- Payroll: calendars, periods, components, salary structures, compensation records, payruns, approval/publish flows, export, and ESS payslips.
- Platform and IAM: multi-tenant scope, role and permission management, access users and roles, correlation IDs, notifications, and auditability.

## Repository layout

- `backend/` - FastAPI app, SQLAlchemy models, Alembic migrations, RQ workers, and backend test suite.
- `backend/app/` - API routers, domain services, middleware, auth and scope logic, and background jobs.
- `backend/alembic/` - Alembic migration history and migration environment.
- `backend/tests/` - Pytest suite, contract coverage, smoke checks, and golden API journeys.
- `frontend/` - Next.js admin and ESS web app, Vitest and Playwright tests, DS components, and feature modules.
- `mobile-application/` - Expo React Native client.
- `docs/` - release, module, testing, production-readiness, and OpenAPI snapshot documentation.
- `scripts/` - release-drill and backend CI helper scripts.
- `docker-compose.yaml` - local multi-service stack for API, web, Postgres, Redis, workers, and test services.

## Architecture at a glance

- Backend: FastAPI with stable JSON envelopes for API responses and standardized error handling.
- Frontend: Next.js app with DS templates, React Query, RTL/MSW tests, and Playwright smoke coverage.
- Jobs and workers: Redis + RQ workers for workflow hooks, HR processing, notifications, and related background work.
- Data: Postgres as the primary system of record, with Alembic-managed schema changes.
- Scope and security: tenant, company, and branch context are fail-closed; correlation IDs are returned in headers and surfaced in error payloads.
- Downloads: document and payroll download endpoints return raw bytes on success and standardized error envelopes on failure paths.

## Local development

### Full stack with Docker

Run the full stack from the repository root:

```bash
docker compose up --build
```

Default local services:

- Web app: `http://localhost:3000`
- Backend API docs: `http://localhost:8000/docs`
- Postgres: `localhost:5432`
- Adminer: `http://localhost:8080`

Notes:

- Migrations run through the `migrate` service during startup.
- Persistent local data is stored under `backend/data/`.
- Local model caches and related assets are stored under `backend/models/`.
- Default local DB credentials in Docker are `attendance / attendance / attendance`.

### Frontend-only development

```bash
cd frontend
npm ci
npm run dev
```

### Backend-only development

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
```

## Testing and release gates

### Frontend

Fast local gate:

```bash
cd frontend
npm ci
npm run lint
npx tsc --noEmit --pretty false
npm run test:ci
npm run build
```

Compose-backed integration gate:

```bash
docker compose up --build --abort-on-container-exit --exit-code-from tests tests
```

Playwright smoke:

```bash
cd frontend
npm run test:e2e -- --project=chromium
```

Release-candidate drill:

```bash
./scripts/rc-check.sh
RUN_E2E=1 ./scripts/rc-check.sh
```

### Backend

Fast backend gate:

```bash
./scripts/backend-ci.sh
```

Backend integration gate:

```bash
./scripts/backend-integration.sh
```

Golden backend journeys:

```bash
RUN_GOLDEN=1 ./scripts/backend-nightly.sh
```

Full backend test entrypoint:

```bash
python3 backend/scripts/run_all_tests.py
```

## CI/CD

Frontend and backend both have GitHub Actions workflows plus local `act` parity.

- Frontend CI and release docs: `docs/CI_CD/CI_CD.md`
- Backend CI docs: `docs/CI_CD/CI_CD_BACKEND.md`
- Frontend release checklist: `docs/CI_CD/PROD_RELEASE_CHECKLIST.md`
- Backend release checklist: `docs/CI_CD/BACKEND_RELEASE_CHECKLIST.md`
- Rollback and deployment references:
  - `docs/CI_CD/ROLLBACK.md`
  - `docs/CI_CD/DEPLOYMENT.md`

If you use `act` locally on Apple Silicon, use `--container-architecture linux/amd64`.

## Documentation map

### Production and readiness

- Production overview: `docs/V0_production.md`
- Frontend production audit: `docs/frontend/V0_PRODUCTION_READINESS_AUDIT.md`
- Testing guidance: `docs/Tests/TESTING_GUIDELINES.md`
- OpenAPI contract snapshot: `docs/openapi/backend.openapi.snapshot.json`

### Frontend milestone docs

- Platform hardening: `docs/frontend/M2_PLATFORM_HARDENING.md`
- Client setup pack: `docs/frontend/M3_CLIENT_SETUP_PACK.md`
- HR Core and Employee 360: `docs/frontend/M4_HR_CORE_EMPLOYEE_360.md`
- Workflow: `docs/frontend/M5_WORKFLOW.md`
- Attendance and Leave: `docs/frontend/M6_ATTENDANCE_LEAVE.md`

### Module packs

- DMS: `docs/Modules/M7_DMS.md`
- Roster and Payables: `docs/Modules/M8_ROSTER_PAYABLES.md`
- Payroll: `docs/Modules/M9_PAYROLL.md`

### Operations and support

- Frontend support runbook: `docs/CI_CD/SUPPORT_RUNBOOK.md`
- Backend support runbook: `docs/CI_CD/BACKEND_SUPPORT_RUNBOOK.md`
- RBAC matrix: `docs/CI_CD/RBAC_MATRIX.md`

## API and platform guarantees

- JSON APIs follow the stable envelope contract:
  - success: `{ "ok": true, "data": ... }`
  - failure: `{ "ok": false, "error": { "code": "...", "message": "...", "details": ..., "correlation_id": "..." } }`
- Successful and failed responses include `X-Correlation-Id`.
- Multi-tenant scope is fail-closed for tenant, company, and branch selection.
- Raw download endpoints keep byte responses on success and standardized error behavior on failure.
- Workflow remains the approval mechanism across leave, attendance correction, DMS verification, payroll approval, and related cross-module actions.

## Security and configuration notes

- Do not commit secrets. Sensitive settings stay env-driven.
- Shared local Docker environments should override the default admin password:

```bash
ADMIN_PASSWORD="your-secret" docker compose up --build
```

- Common environment-driven integrations include API keys, service-account paths, and storage settings; keep them outside the repository.

## Recommended starting points

- Product and rollout context: `docs/V0_production.md`
- Frontend release process: `docs/CI_CD/PROD_RELEASE_CHECKLIST.md`
- Backend release process: `docs/CI_CD/BACKEND_RELEASE_CHECKLIST.md`
- Local and GitHub CI usage: `docs/CI_CD/CI_CD.md` and `docs/CI_CD/CI_CD_BACKEND.md`
