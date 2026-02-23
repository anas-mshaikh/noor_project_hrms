# HR Profile Change v1 (Milestone 6)

This repo includes a first-class **HR Profile Change** domain integrated with
**Workflow Engine v1**.

Design principle:
- `hr_core.profile_change_requests` stores canonical change requests (`change_set`,
  status, linkage to workflow).
- Workflow stores the approval process and in-app notifications.
- The two are linked via:
  - `workflow.requests.entity_type = "hr_core.profile_change_request"`
  - `workflow.requests.entity_id = hr_core.profile_change_requests.id`

On terminal workflow transitions, the workflow engine invokes a domain hook
(`entity_type` handler) that applies approved changes to `hr_core.*` in the
**same DB transaction** as the workflow decision.

## Database

Schema: `hr_core`

Table: `hr_core.profile_change_requests`
- Tenant-scoped domain record linked to workflow.
- Idempotency:
  - partial unique index `(tenant_id, employee_id, idempotency_key)` where
    `idempotency_key IS NOT NULL`.

## Workflow integration

Request type code:
- `HR_PROFILE_CHANGE` (seeded via Alembic)

For submissions to work, the tenant must have an **active** workflow definition
for `HR_PROFILE_CHANGE`.
Common v1 definition:
- step 0: `MANAGER`
(Optionally add HR step later using `ROLE(HR_ADMIN)`.)

Terminal hook behavior:
- `approved`:
  - locks `hr_core.profile_change_requests` row `FOR UPDATE`
  - applies `change_set` to `hr_core.*` (see apply semantics below)
  - sets request status `APPROVED`, decided fields
  - inserts audit row `hr.profile_change.approved`
  - emits in-app notification outbox rows (dedupe) to the subject employee's linked user(s)
- `rejected`:
  - sets status `REJECTED`, decided fields
  - inserts audit row `hr.profile_change.rejected`
  - emits notification outbox rows (dedupe)
- `cancelled`:
  - sets status `CANCELED` (idempotent)
  - inserts audit row `hr.profile_change.cancelled`

All side-effects happen inside the same DB transaction as the workflow transition.

## Change set schema (v1)

The request payload is a controlled `change_set` object. Unknown keys are rejected.

Supported top-level keys:
- `phone`: `string | null` (trimmed, max 32)
- `address`: `object | null` (replace semantics; `null` clears to `{}`)
- `bank_accounts`: `list[BankAccount]` (replace-all semantics on apply)
- `government_ids`: `list[GovernmentId]` (replace-all semantics on apply)
- `dependents`: `list[Dependent]` (replace-all semantics on apply)

`BankAccount`:
- `iban`: `string | null` (<=64)
- `account_number`: `string | null` (<=64)
- `bank_name`: `string | null` (<=200)
- `is_primary`: `bool | null`
Rules:
- require `iban` OR `account_number`
- at most one primary
- if none primary, the first item becomes primary (deterministic)

`GovernmentId`:
- `id_type`: `string` (<=64, required)
- `id_number`: `string` (<=128, required)
- `issued_at`: `YYYY-MM-DD | null`
- `expires_at`: `YYYY-MM-DD | null`
- `issuing_country`: `string | null`
- `notes`: `string | null`

`Dependent`:
- `name`: `string` (<=200, required)
- `relationship`: `string | null`
- `dob`: `YYYY-MM-DD | null`

## Apply semantics (v1, deterministic)

Only keys present in `change_set` are applied.

- `phone`:
  - patches `hr_core.persons.phone`
- `address`:
  - replaces `hr_core.persons.address`
  - `address = null` is normalized to `{}` (clear)
- `bank_accounts`:
  - replace-all in `hr_core.employee_bank_accounts` (delete then insert)
- `government_ids`:
  - replace-all in `hr_core.employee_government_ids`
- `dependents`:
  - replace-all in `hr_core.employee_dependents`

## Permissions (colon-style)

Seeded via Alembic and mapped to default roles:
- `hr:profile-change:submit`
- `hr:profile-change:read`
- `hr:profile-change:apply`

## API (all under `/api/v1`, enveloped JSON responses)

ESS:
- `POST /ess/me/profile-change-requests`
- `GET  /ess/me/profile-change-requests?status=&limit=&cursor=`
- `POST /ess/me/profile-change-requests/{id}/cancel`

HR:
- `GET /hr/profile-change-requests?status=&branch_id=&limit=&cursor=`

Approvals are performed via workflow:
- `GET  /workflow/inbox`
- `POST /workflow/requests/{request_id}/approve`
- `POST /workflow/requests/{request_id}/reject`

## Errors (v1)

- `hr.profile_change.not_found` (404 participant-safe)
- `hr.profile_change.invalid_change_set` (400)
- `hr.profile_change.idempotency_conflict` (409)
- `hr.profile_change.already_terminal` (409)

