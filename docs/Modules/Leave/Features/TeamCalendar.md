# Team Calendar

This feature supplements `docs/Modules/Leave/Leave.Internal.md`.

## Overview
MSS team calendar shows approved leave spans for the manager's team.

## Purpose
Give managers operational visibility without exposing full leave-admin setup.

## Rules
- Requires `leave:team:read`.
- Uses a bounded date range and manager depth selection.
- Shows approved leave spans, not the full pending approval queue.

## Flows
- Open `/leave/team-calendar`
- Change month and depth
- Select a day for detail
- Use Workflow Inbox for approvals

## Screens
- `/leave/team-calendar`

## Backend/API notes
- `GET /api/v1/leave/team/calendar`

## DB notes
- Reads from leave requests and request-day expansion via service logic.

## Edge cases
- invalid date range
- missing company scope on the frontend
- empty month

## Errors
- `leave.invalid_range`
- frontend scope-required states

## Tests
- `frontend/src/app/leave/team-calendar/__tests__/page.test.tsx`

## Open questions
- Confirm final customer wording for direct-vs-all team depth.
