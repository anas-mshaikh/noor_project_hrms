# Attendance Corrections

This feature supplements `docs/Modules/Attendance/Attendance.Internal.md`.

## Overview
Attendance corrections let employees request deterministic day-status overrides that are approved through Workflow.

## Purpose
Correct attendance outcomes without mutating raw source data.

## Rules
- Leave conflict blocks correction create and approve paths.
- Pending uniqueness prevents multiple open corrections for the same day.
- Approval writes `attendance.day_overrides`.

## Flows
- Submit correction
- Review correction history
- Cancel pending correction
- Approve or reject through Workflow Inbox

## Screens
- `/attendance/corrections`
- `/attendance/corrections/new`

## Backend/API notes
- `POST /api/v1/attendance/me/corrections`
- `GET /api/v1/attendance/me/corrections`
- `POST /api/v1/attendance/me/corrections/{correction_id}/cancel`
- `GET /api/v1/attendance/corrections`

## DB notes
- `attendance.attendance_corrections`
- `attendance.day_overrides`

## Edge cases
- too old
- future day blocked
- leave conflict
- duplicate pending request

## Errors
- `attendance.correction.too_old`
- `attendance.correction.future_not_allowed`
- `attendance.correction.conflict.leave`
- `attendance.correction.pending_exists`

## Tests
- `backend/tests/domains/attendance/api/test_attendance_regularization.py`
- `frontend/src/app/attendance/corrections/__tests__/page.test.tsx`
- `frontend/src/app/attendance/corrections/new/__tests__/page.test.tsx`

## Open questions
- Verify the final admin reporting UX for correction reviews.
