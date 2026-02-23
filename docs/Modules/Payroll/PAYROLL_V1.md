# Payroll Foundation v1 (Milestone 9)

This document describes the Payroll Foundation v1 module:

- Setup primitives: calendars/periods, components, salary structures, employee compensations
- Payrun engine: deterministic generation of per-employee payrun items/lines
- Approval via Workflow Engine v1 (`PAYRUN_APPROVAL`)
- Publishing payslips as JSON stored in DMS (LOCAL storage in v1)
- API surface (`/api/v1`) + permissions + security rules

Non-goals for v1:
- country-specific taxes (PF/ESI/WPS/etc.)
- advanced overtime/grace policies
- PDF rendering (payslip is JSON file only)
- bank payment integrations (CSV export is a placeholder)

## Core Principles

1) Deterministic:
- same inputs => same outputs
- line items materialized into immutable tables for fast reads

2) Auditable:
- payrun generate/submit/approve/reject/publish actions are written to `audit.audit_log`

3) Safe:
- tenant-scoped queries everywhere
- employee payslip reads are participant-only (404 on deny)
- branch-scoped admin tokens cannot access other branches (404/400 based on endpoint)

4) Scalable:
- batch queries (avoid N+1)
- payrun outputs stored in `payroll.payrun_items` / `payroll.payrun_item_lines`

## Data Model

Schema: `payroll`

### Setup tables

- `payroll.calendars`
  - monthly calendars (`frequency='MONTHLY'`) with `currency_code` and `timezone`
  - unique `(tenant_id, code)`

- `payroll.periods`
  - period_key format: `YYYY-MM`
  - inclusive date range `[start_date, end_date]`
  - unique `(tenant_id, calendar_id, period_key)`

- `payroll.components`
  - tenant-scoped catalog of EARNING/DEDUCTION components
  - calc modes: `FIXED`, `PERCENT_OF_GROSS`, `MANUAL`
  - unique `(tenant_id, code)`

- `payroll.salary_structures`
  - reusable structure definitions
  - unique `(tenant_id, code)`

- `payroll.salary_structure_lines`
  - ordered list of components per structure
  - optional overrides on calc mode / amount / percent
  - unique `(tenant_id, salary_structure_id, component_id)`

- `payroll.employee_compensations`
  - effective-dated compensation referencing a structure
  - `base_amount` is a monthly base in v1
  - partial unique: one active row per employee where `effective_to IS NULL`

### Payrun tables

- `payroll.payruns`
  - unique `(tenant_id, period_id, branch_id, version)`
  - v1 uses `version=1` only (revisions are a future milestone)
  - lifecycle:
    - `DRAFT` -> `PENDING_APPROVAL` -> `APPROVED` -> `PUBLISHED`
  - `totals_json` stores aggregate totals and counts

- `payroll.payrun_items` (immutable per employee for a payrun)
  - unique `(tenant_id, payrun_id, employee_id)`
  - `computed_json` stores the computation breakdown for traceability
  - v1 can set `status='EXCLUDED'` with `anomalies_json` for missing inputs

- `payroll.payrun_item_lines` (immutable component-level line items)
  - denormalizes `component_code` / `component_type` for stability

### Payslips

- `payroll.payslips`
  - unique `(tenant_id, payrun_id, employee_id)`
  - points to `dms.documents` via `dms_document_id`
  - v1 publishes payslips as JSON files stored in DMS:
    - `dms.document_types.code = 'PAYSLIP'`
    - `dms.documents.owner_employee_id = employee_id`
    - `dms.document_versions.file_id` points to the JSON file in `dms.files`

## Calculation Model (v1)

Inputs:
- `payroll.employee_compensations.base_amount` (monthly base)
- `attendance.payable_day_summaries` for the period date range:
  - `day_type`, `presence_status`, `payable_minutes`

Aggregation (per employee):
- `working_days_in_period` = count of summary rows where `day_type='WORKDAY'`
- `payable_days` = count where `day_type='WORKDAY' AND presence_status='PRESENT'`
- `payable_minutes` = sum of `payable_minutes`

Proration:
- `proration_factor = payable_days / max(working_days_in_period, 1)`
- `prorated_base = base_amount * proration_factor`

Components:
- `FIXED`:
  - amount = `line.amount_override` else `component.default_amount` else 0
- `PERCENT_OF_GROSS`:
  - percent = `line.percent_override` else `component.default_percent` else 0
  - percent base (deterministic): `percent_base_gross = prorated_base + fixed_earnings_total`
  - amount = `percent_base_gross * (percent / 100)`
- `MANUAL`:
  - amount = 0 in v1 (placeholder for future adjustment inputs)

Totals:
- `gross_amount = prorated_base + earnings_total`
- `deductions_amount = deductions_total`
- `net_amount = gross_amount - deductions_amount`

Rounding:
- Use Decimal math and quantize to 2dp with `ROUND_HALF_UP`.

Missing data handling (fail-safe):
- No effective compensation for period: payrun_item is `EXCLUDED` with anomaly `NO_COMPENSATION`.
- No payable summaries: `EXCLUDED` with anomaly `NO_PAYABLE_SUMMARIES`.
- Currency mismatch with calendar currency: `EXCLUDED` with anomaly `CURRENCY_MISMATCH`.

## Workflow Integration (PAYRUN_APPROVAL)

Request type:
- `workflow.request_types.code = 'PAYRUN_APPROVAL'`

Entity mapping:
- `workflow.requests.entity_type = 'payroll.payrun'`
- `workflow.requests.entity_id = payroll.payruns.id`

Submit behavior:
- `POST /api/v1/payroll/payruns/{payrun_id}/submit-approval`
- Locks the payrun row and creates a workflow request.
- Updates payrun status to `PENDING_APPROVAL`.

Terminal hook behavior:
- On APPROVED: set payrun status to `APPROVED` (idempotent)
- On REJECTED: set payrun status to `DRAFT` and clear `workflow_request_id` (idempotent)
- Hook runs inside the workflow transaction (no commits inside handler).

Important:
- Workflow engine requires the requester user to be linked to an employee
  (`hr_core.employee_user_links`). Tests and real deployments must ensure
  payroll admins are linked.

## Publishing Payslips

Endpoint:
- `POST /api/v1/payroll/payruns/{payrun_id}/publish`

Rules:
- Only allowed when payrun status is `APPROVED`.
- Locks the payrun row FOR UPDATE.
- Generates payslip JSON for each INCLUDED payrun_item.
- Stores JSON as DMS file/document/version and links it to `payroll.payslip`.
- Sets payrun status to `PUBLISHED`.
- Emits in-app notification outbox rows:
  - `template_code='payroll.payslip.published'`
  - dedupe key: `payslip:published:<payrun_id>:<employee_id>:<user_id>`

## API Surface

All JSON endpoints use the stable envelope:
- success: `{ "ok": true, "data": ... }`
- error: `{ "ok": false, "error": { "code": "...", ... } }`

### Admin / Payroll APIs (`/api/v1/payroll/*`)

Calendars/periods:
- `POST /api/v1/payroll/calendars`
- `GET  /api/v1/payroll/calendars`
- `POST /api/v1/payroll/calendars/{calendar_id}/periods`
- `GET  /api/v1/payroll/calendars/{calendar_id}/periods?year=YYYY`

Components:
- `POST /api/v1/payroll/components`
- `GET  /api/v1/payroll/components?type=EARNING|DEDUCTION`

Salary structures:
- `POST /api/v1/payroll/salary-structures`
- `POST /api/v1/payroll/salary-structures/{structure_id}/lines`
- `GET  /api/v1/payroll/salary-structures/{structure_id}`

Employee compensation:
- `POST /api/v1/payroll/employees/{employee_id}/compensation`
- `GET  /api/v1/payroll/employees/{employee_id}/compensation`

Payruns:
- `POST /api/v1/payroll/payruns/generate`
- `GET  /api/v1/payroll/payruns/{payrun_id}?include_lines=0|1`
- `POST /api/v1/payroll/payruns/{payrun_id}/submit-approval`
- `POST /api/v1/payroll/payruns/{payrun_id}/publish`
- `GET  /api/v1/payroll/payruns/{payrun_id}/export?format=csv` (raw CSV bytes)

### ESS Payslip APIs (`/api/v1/ess/*`)

- `GET /api/v1/ess/me/payslips?year=YYYY`
- `GET /api/v1/ess/me/payslips/{payslip_id}`
- `GET /api/v1/ess/me/payslips/{payslip_id}/download` (raw JSON bytes)

Participant-safe rule:
- Employees can only see their own payslips; others return 404.

## Permissions Matrix (v1)

Setup:
- `payroll:calendar:read`, `payroll:calendar:write`
- `payroll:component:read`, `payroll:component:write`
- `payroll:structure:read`, `payroll:structure:write`
- `payroll:compensation:read`, `payroll:compensation:write`

Payruns:
- `payroll:payrun:generate`, `payroll:payrun:read`, `payroll:payrun:submit`,
  `payroll:payrun:publish`, `payroll:payrun:export`

Payslips:
- `payroll:payslip:read` (ESS self)

## Future Extension Points

- Payrun revisions/versioning (version > 1 with full history)
- Manual adjustments and retro pay
- Country packs (tax rules modules)
- PDF payslip rendering
- Bank export formats (WPS, ACH, etc.)
- Payroll month locking and retro adjustments

