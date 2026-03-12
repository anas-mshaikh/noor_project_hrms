# Payrun Approval

This feature supplements `docs/Modules/Payroll/Payroll.Internal.md`.

## Overview
Payrun approval moves payroll from draft generation to approved and published states through Workflow.

## Purpose
Keep payroll approval auditable and avoid duplicate approval systems.

## Rules
- Submit approval only from `DRAFT`.
- Publish only from `APPROVED`.
- ESS payslips become available after publish.

## Flows
- Generate payrun
- Submit approval
- Approver acts in Workflow
- Payroll admin publishes
- Employee downloads payslip

## Screens
- `/payroll/payruns`
- `/payroll/payruns/[payrunId]`
- `/workflow/inbox`
- `/ess/payslips`

## Backend/API notes
- `POST /api/v1/payroll/payruns/generate`
- `GET /api/v1/payroll/payruns/{payrun_id}`
- `POST /api/v1/payroll/payruns/{payrun_id}/submit-approval`
- `POST /api/v1/payroll/payruns/{payrun_id}/publish`
- `GET /api/v1/payroll/payruns/{payrun_id}/export`

## DB notes
- `payroll.payruns`
- `payroll.payrun_items`
- `payroll.payrun_item_lines`
- `payroll.payslips`

## Edge cases
- invalid payrun state
- missing workflow definition
- participant-safe payslip deny

## Errors
- `payroll.payrun.invalid_state`
- `payroll.payrun.not_approved`
- `workflow.definition.no_active`
- `payroll.payslip.not_found`

## Tests
- `backend/tests/domains/payroll/api/test_payroll_v1.py`
- `frontend/src/app/payroll/payruns/[payrunId]/__tests__/page.test.tsx`
- `frontend/src/app/__tests__/m9.stories.test.tsx`

## Open questions
- Confirm long-term release/export packaging beyond CSV and JSON payslips.
