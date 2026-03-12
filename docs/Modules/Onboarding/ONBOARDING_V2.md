# Onboarding v2 (Milestone 6)

This repo includes a first-class **Onboarding v2** domain under schema `onboarding`.

Design principle:
- Onboarding stores canonical templates, bundles, and tasks as first-class rows.
- Workflow is reused for approvals where needed (document verification, profile
  change approvals).
- DMS is the canonical file/document system of record for onboarding document uploads.

## Database

Schema: `onboarding`

Tables:
- `onboarding.plan_templates`
  - tenant-scoped onboarding plan templates (`code`, `name`, `is_active`, optional scope fields)
- `onboarding.plan_template_tasks`
  - tasks per template (`DOCUMENT`, `FORM`, `ACK`)
- `onboarding.employee_bundles`
  - one active bundle per employee (partial unique where `status='ACTIVE'`)
- `onboarding.employee_tasks`
  - snapshot of template tasks at bundle creation time
  - contains submission status and DMS/workflow linkage fields:
    - `related_document_id` (for DOCUMENT tasks)
    - `verification_workflow_request_id` (when doc verification is required)

## Task types (v1)

Supported `task_type` values:
- `DOCUMENT`
  - Employee uploads a file.
  - The system creates/versions an employee-owned DMS document of
    `required_document_type_code`.
  - If `requires_document_verification=true`, a `DOCUMENT_VERIFICATION` workflow
    request is created for that document and stored on the task.
  - If verification is NOT required, the task is marked `APPROVED` immediately.
- `FORM`
  - Employee submits JSON payload.
  - Task status becomes `SUBMITTED`.
  - Payload can later be mapped into an HR Profile Change request via "Submit packet".
- `ACK`
  - Simple acknowledgement placeholder in v1.
  - Task status becomes `APPROVED` and stores `{ "ack": true }` as payload.

Customization placeholders:
- Add new task types later (security checks, equipment pickup, etc.).
- Add additional assignee resolution strategies if needed.

## DMS integration (DOCUMENT tasks)

Document upload flow:
1) Upload bytes using DMS file service (LOCAL storage v1).
2) Create a DMS employee document for `(tenant, employee, document_type_code)`:
   - if an active document exists, add a new version
   - otherwise create a new document
3) Link onboarding task to the document (`related_document_id`).
4) If verification is required:
   - create `DOCUMENT_VERIFICATION` workflow request for the document
   - store `verification_workflow_request_id` on the task
   - mirror the uploaded file into `workflow.request_attachments` (idempotent)

When a document verification workflow reaches terminal state, the DMS hook updates
any onboarding tasks referencing that document:
- VERIFIED -> onboarding task status `APPROVED`
- REJECTED -> onboarding task status `REJECTED`
This avoids polling on the onboarding read path.

## Profile change integration ("Submit packet")

The onboarding packet flow collects submitted FORM tasks and creates ONE
HR Profile Change request (`HR_PROFILE_CHANGE` workflow).

Mapping contract (v1):
- `onboarding.plan_template_tasks.form_profile_change_mapping` is a JSON object:
  `{ "<target_field>": "<source_key>" }`
- `target_field` in: `phone`, `address`, `bank_accounts`, `government_ids`, `dependents`
- `source_key` is a top-level key in the task's `submission_payload`

Deterministic merge:
- tasks are processed by `order_index ASC`
- for each mapping entry where `source_key` exists in payload:
  - set `change_set[target_field] = value`
  - later tasks overwrite earlier values ("last write wins")

Idempotency:
- packet submission uses idempotency key `onboarding:<bundle_id>` for the profile change request

## Permissions (colon-style)

Seeded via Alembic and mapped to default roles:
- `onboarding:template:read`
- `onboarding:template:write`
- `onboarding:bundle:read`
- `onboarding:bundle:write`
- `onboarding:task:read`
- `onboarding:task:submit`

## API (all under `/api/v1`, enveloped JSON responses)

HR (templates + bundles):
- `GET  /onboarding/plan-templates`
- `POST /onboarding/plan-templates`
- `POST /onboarding/plan-templates/{template_id}/tasks`
- `POST /onboarding/employees/{employee_id}/bundle`
- `GET  /onboarding/employees/{employee_id}/bundle`

ESS (bundle + task submissions):
- `GET  /ess/me/onboarding`
- `POST /ess/me/onboarding/tasks/{task_id}/submit-form`
- `POST /ess/me/onboarding/tasks/{task_id}/upload-document` (multipart file)
- `POST /ess/me/onboarding/tasks/{task_id}/ack`
- `POST /ess/me/onboarding/bundle/{bundle_id}/submit-packet`

## Errors (v1)

Onboarding:
- `onboarding.template.not_found`
- `onboarding.bundle.not_found`
- `onboarding.bundle.already_exists`
- `onboarding.task.not_found` (participant-safe)
- `onboarding.task.type_mismatch`
- `onboarding.task.not_editable`
- `onboarding.packet.no_submissions`

Profile change errors may surface during submit-packet validation:
- `hr.profile_change.invalid_change_set`
- `hr.profile_change.idempotency_conflict`

