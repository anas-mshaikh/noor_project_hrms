# DB vNext (Enterprise HRMS Foundation)

DB vNext is an enterprise-ready HRMS foundation schema that lives **in the same Postgres database** as the current product modules, but in **separate Postgres schemas** for clean domain boundaries:

- `tenancy`: multi-tenant org hierarchy (tenant → company → branch → org units, job titles, grades)
- `iam`: users/roles/permissions and scoped role assignments
- `hr_core`: employee 360 master record (person, employee, employment history, contracts, IDs, bank, dependents)
- `workflow`: generic requests + multi-level approvals
- `dms`: document management + expiry alert foundation

## What changed

As of **2026-02-17**, the historical Alembic chain was **squashed** into a single
baseline revision for single-developer velocity:

- Baseline revision: `backend/alembic/versions/000000000000_baseline_squash.py`
- Baseline SQL payload: `backend/alembic/versions/000000000000_baseline.sql`
- Historical revisions (archived for reference only): `backend/alembic/versions_archive/`

The baseline creates the full schema (all `*_vnext` foundations + later module
extensions) and inserts the minimum required global seed rows (roles,
permissions, request types, role-permission mappings) so a fresh DB can boot.

Previously, multiple Alembic revisions incrementally added DB vNext foundation
objects (now archived under `backend/alembic/versions_archive/`):

- `backend/alembic/versions_archive/888da65cf59f_db_vnext_0001_core_foundation.py`
  - Creates extensions: `pgcrypto`, `citext`, `pg_trgm`
  - Creates schemas: `tenancy`, `iam`, `hr_core`, `workflow`, `dms`
  - Creates `public.set_updated_at()` and adds updated_at triggers to mutable tables
  - Creates the vNext core tables + indexes
- `backend/alembic/versions_archive/fc4c56b52118_db_vnext_0002_seed_defaults.py`
  - Seeds base roles + permissions + request types
- `backend/alembic/versions_archive/aca6f7cb881b_db_vnext_0003_seed_demo_tenant.py`
  - Opt-in demo seed (env var: `DB_VNEXT_SEED_DEMO_TENANT=1`): demo tenant/company/branch + demo document types
- `backend/alembic/versions_archive/b3f7a9d2c4e1_db_vnext_0004_drop_legacy_identity.py`
  - Drops legacy identity duplicates (e.g. `core.*` masters) after asserting vNext tables exist
- `backend/alembic/versions_archive/c4e1b3f7a9d2_db_vnext_0005_rewire_module_fks.py`
  - Renames legacy columns (`org_id`→`tenant_id`, `store_id`→`branch_id`) and rewires module FKs to vNext masters
- `backend/alembic/versions_archive/d5a2c6e8f1b3_db_vnext_0006_db_hardening.py`
  - Adds enterprise hardening: status CHECK constraints, critical indexes, helper views, and selected updated_at triggers
- `backend/alembic/versions_archive/8c028d85bff3_db_vnext_0007_reconcile_iam_users_email.py`
  - Reconciles drifted dev DB volumes where `iam.users.email` was missing (forward-only fix)
- `backend/alembic/versions_archive/88e00e12d1a9_db_vnext_0008_reconcile_hr_core_persons_email.py`
  - Reconciles drifted dev DB volumes where `hr_core.persons.email` was missing (forward-only fix)
- `backend/alembic/versions_archive/78a23d4f40ba_db_vnext_0009_module_tenant_id_rbac_ready.py`
  - Adds `tenant_id` to key module/business tables (analytics, face, HR module tables, vision pipeline) for simpler tenant filtering and future RLS
- `backend/alembic/versions_archive/85a23039697f_iam_refresh_tokens.py`
  - Adds `iam.refresh_tokens` for JWT refresh token storage (used by `/api/v1/auth/*`)
- `backend/alembic/versions_archive/6e4f83bf4ad6_seed_colon_permissions.py`
  - Seeds colon-style permission vocabulary and role-permission mappings for permission-driven enforcement
- `backend/alembic/versions_archive/a2ce7edbde24_audit_log.py`
  - Adds `audit.audit_log` for tenant-scoped critical action auditing
- `backend/alembic/versions_archive/571e947ad55d_workflow_notifications.py`
  - Adds `workflow.notifications` for in-app notification inbox delivery

## Canonical masters (authoritative source of truth)

These schemas are authoritative and must be treated as the **only** masters:

- `tenancy`: tenants / companies / branches / org units
- `iam`: users / roles / permissions / role assignments
- `hr_core`: persons / employees / employment history
- `workflow`: requests / approvals
- `dms`: files / documents / expiry rules

Canonical ID mapping for module schemas:

- `tenant_id` → `tenancy.tenants.id`
- `company_id` → `tenancy.companies.id`
- `branch_id` → `tenancy.branches.id`
- `employee_id` → `hr_core.employees.id`

## Milestone 1 runtime guarantees

- Branch-first API shape: legacy `/api/v1/stores*` and `/api/v1/organizations*` are removed.
- Tenant isolation is fail-closed at runtime (tenant context required for protected operations).
- Permission checks are enforced via IAM permissions (not role-name checks).
- Request correlation id is emitted via `X-Correlation-Id` and carried in structured error/log context.
- Critical IAM/HR mutations are written to `audit.audit_log`.
- In-app notifications are produced into `workflow.notification_outbox` and consumed into `workflow.notifications`.

## Legacy removal (0004–0006)

This repo intentionally supports a **hard cutover** because there is no production data.

- 0004 drops legacy identity duplicates (example: the old `core.organizations/stores/employees` masters).
- 0005 rewires module schemas (`attendance/vision/face/hr/mobile/imports/work/...`) to reference vNext via foreign keys.
- 0006 hardens vNext with CHECK constraints, indexes, and helper views.

## How to reset dev DB

Full reset (recommended in dev): recreate the Postgres volume and rerun migrations.

```bash
docker compose down -v
docker compose up --build
```

Note: downgrade is intentionally **not supported** (legacy tables were deleted during the cutover). Use a full reset (`docker compose down -v`) to return to a clean state.

If you had an existing dev volume from before the squash, you have two options:

1) Wipe the volume (simplest): `docker compose down -v`
2) Stamp the existing volume to the new baseline (no data loss):
   - Rebuild + run migrations once: `docker compose up --build migrate`
   - Then update Alembic's version metadata:
     ```bash
     docker compose exec -T db psql -U attendance -d attendance -c \
       "update alembic_version set version_num='000000000000';"
     ```

After a full reset, create the first tenant/admin via `POST /api/v1/bootstrap` (see `docs/API_CORE.md`).

## How to run migrations

In Docker Compose, migrations run automatically via the `migrate` service.

To run manually:

```bash
docker compose run --rm migrate alembic upgrade head
```

## Smoke test

The DB vNext smoke test:

- Inserts a tenant/company/branch
- Inserts a user and an employee master record
- Assigns roles
- Creates a workflow definition + request + approval step
- Attaches a file to a request
- Optionally validates rewired module FKs by inserting into `attendance.attendance_daily` and `face.employee_faces`
- Verifies key indexes exist

Note: the smoke test runs inside a transaction and rolls back at the end, so it does not leave demo data behind.

Run:

```bash
python3 backend/scripts/db_vnext_smoke_test.py
```

In Docker Compose, this runs automatically after migrations as part of the `tests` service.

## ER overview (high level)

**tenancy**
- `tenancy.tenants` → `tenancy.companies` → `tenancy.branches`
- `tenancy.org_units` (self-parent, optionally branch-scoped)
- `tenancy.job_titles`, `tenancy.grades` (company-scoped)

**iam**
- `iam.users`
- `iam.roles`, `iam.permissions`, `iam.role_permissions`
- `iam.user_roles` (scoped: tenant + optional company/branch)
- `iam.api_tokens` (tenant-scoped)

**hr_core**
- `hr_core.persons` → `hr_core.employees`
- `hr_core.employee_employment` (history + manager)
- `hr_core.employee_user_links` (employee ↔ user)
- `hr_core.employee_contracts`, `employee_dependents`, `employee_bank_accounts`, `employee_government_ids`

**workflow**
- `workflow.request_types`
- `workflow.workflow_definitions` → `workflow.workflow_definition_steps`
- `workflow.requests` → `workflow.request_steps` / `workflow.request_comments` / `workflow.request_attachments`
- `workflow.notification_outbox`

**dms**
- `dms.files`
- `dms.document_types` → `dms.documents` → `dms.document_versions`
- `dms.document_links` (polymorphic links to any entity)
- `dms.expiry_rules` → `dms.expiry_events`

## Future modules

Future modules (leave, payroll, separation, expenses, assets) should extend:

- `hr_core` for employee master data extensions, policies and entitlements
- `workflow` for request/approval flows (multi-step + audit trail)
- `dms` for document storage, expiry, and compliance alerts
