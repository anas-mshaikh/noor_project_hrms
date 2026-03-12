# Leave Policies

This feature supplements `docs/Modules/Leave/Leave.Internal.md`.

## Overview
Leave policies define entitlements and leave-type rules for employees.

## Purpose
Separate setup concerns from request execution and make leave behavior effective-dated and auditable.

## Rules
- Policies must be active and effective for the employee.
- Rules are defined per leave type.
- Employee policy assignment is effective-dated.

## Flows
- Create leave type
- Create policy
- Upsert rules
- Assign policy to employee
- Allocate balances
- Configure weekly off and holidays

## Screens
- Needs Verification in the current web UI.

## Backend/API notes
- `GET/POST /api/v1/leave/types`
- `GET/POST /api/v1/leave/policies`
- `POST /api/v1/leave/policies/{policy_id}/rules`
- `POST /api/v1/leave/employees/{employee_id}/policy`
- `POST /api/v1/leave/allocations`
- `GET/PUT /api/v1/leave/calendar/weekly-off`
- `GET/POST /api/v1/leave/calendar/holidays`

## DB notes
- `leave.leave_types`
- `leave.leave_policies`
- `leave.leave_policy_rules`
- `leave.employee_leave_policy`
- `leave.weekly_off`
- `leave.holidays`

## Edge cases
- missing weekly off rows
- policy/employee company mismatch
- policy not yet effective

## Errors
- `leave.policy.missing`
- `leave.calendar.missing`
- `leave.type.not_found`
- `leave.policy.rule.missing`

## Tests
- `backend/tests/domains/leave/api/test_leave_management.py`

## Open questions
- Verify the exact shipped admin UX for setup and reporting.
