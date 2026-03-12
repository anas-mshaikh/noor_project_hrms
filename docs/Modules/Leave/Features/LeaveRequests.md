# Leave Requests

This feature supplements `docs/Modules/Leave/Leave.Internal.md`.

## Overview
ESS leave requests are the employee-facing entry point for leave operations.

## Purpose
Capture leave intent, validate policy and balance rules, link to workflow, and provide a deterministic request history.

## Rules
- Requires active policy, rule, branch calendar, and valid dates.
- Enforces overlap and idempotency safeguards.
- Can require DMS attachments depending on leave-type rules.

## Flows
- Submit request from `/leave`
- Review workflow link in request history
- Cancel while still pending

## Screens
- `/leave`

## Backend/API notes
- `GET /api/v1/leave/me/balances`
- `GET /api/v1/leave/me/requests`
- `POST /api/v1/leave/me/requests`
- `POST /api/v1/leave/me/requests/{leave_request_id}/cancel`

## DB notes
- `leave.leave_requests`
- `leave.leave_request_days`
- `leave.leave_ledger`

## Edge cases
- overlap
- insufficient balance
- half-day validation
- idempotency conflicts
- leave-year boundary violations

## Errors
- `leave.overlap`
- `leave.insufficient_balance`
- `leave.half_day.invalid`
- `leave.idempotency.conflict`

## Tests
- `backend/tests/domains/leave/api/test_leave_management.py`
- `frontend/src/app/leave/__tests__/page.test.tsx`

## Open questions
- Verify exact customer guidance for HR-admin request visibility.
