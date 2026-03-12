# Architecture

## System shape

Noor HRMS is a multi-tenant platform composed of:
- a FastAPI backend under `backend/app/`
- a Next.js web application under `frontend/`
- Redis-backed workers for asynchronous tasks
- Postgres as the system of record
- Alembic-managed schema changes

## Backend structure

- `backend/app/api/router.py` wires legacy and domain routers into the `/api/v1` surface.
- `backend/app/domains/*` contains the active HRMS business domains.
- `backend/app/api/v1/*` contains older or cross-cutting API surfaces such as openings, screening runs, imports, cameras, videos, and tasks.
- `backend/app/core/*` owns cross-cutting behavior such as config, logging, middleware, errors, and response helpers.

## Frontend structure

- `frontend/src/app/*` contains route pages.
- `frontend/src/features/*` contains feature-first API wrappers, query keys, components, and utilities.
- `frontend/src/components/ds/*` contains shared design-system components and templates.

## Cross-cutting foundations

- API responses use a stable success/error envelope for JSON endpoints.
- Raw download endpoints keep bytes on success and standardized envelope behavior on error.
- `TraceIdMiddleware` adds correlation IDs to requests and responses.
- Scope selection is fail-closed for tenant, company, and branch-sensitive flows.
- Workflow is the shared approval backbone for leave, attendance corrections, DMS verification, profile change, onboarding packet flows, and payroll approval.

## Legacy vs active areas

Active HRMS modules live primarily in `backend/app/domains/*` and modern frontend routes under `frontend/src/app/*`.

Legacy or transitional areas still present in the repo include:
- cameras, videos, jobs, results, and face-system processing
- admin import flows
- mobile mapping/support docs

These areas are retained, but they are not positioned as primary HRMS modules in the new docs structure.
