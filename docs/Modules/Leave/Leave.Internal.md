# Leave

## 1. Overview
- Purpose: manage leave setup, employee leave balances, leave requests, team leave visibility, and workflow-driven approval side effects.
- Business value: gives HR a configurable leave program while keeping employee requests, balances, approval history, and attendance impact deterministic.
- Summary: the module spans HR admin setup, ESS request flows, MSS team calendar visibility, and workflow-backed finalization.

## 2. Scope
- In scope: leave types, leave policies, policy rules, employee policy assignment, allocations, weekly off, holidays, ESS balances, ESS request list, ESS submit/cancel, MSS team calendar, usage reporting, workflow linkage, attendance override side effects, and DMS-backed attachments.
- Out of scope: policy simulation tooling, complex regional compliance rules, non-working-day forecasting UX beyond the current routes, and any behavior not verified in `backend/app/domains/leave/*`, current frontend routes, or existing leave docs.

## 3. Personas and Roles
- Employee: reads balances and requests, submits leave, cancels pending requests.
- Manager: reads team calendar and acts through workflow inbox approvals.
- HR admin: configures leave types, policies, rules, assignments, allocations, weekly off, holidays, and usage reports.
- Workflow approver: approves or rejects `LEAVE_REQUEST` items through Workflow.

## 4. Module Capabilities
- ESS balances by leave type and year.
- ESS leave request listing with pagination and status filtering.
- ESS leave request submission with idempotency and optional DMS attachments.
- ESS cancel of pending leave requests.
- MSS team calendar for approved leave spans.
- HR leave type catalog management.
- HR leave policy and policy-rule management.
- HR employee policy assignment and balance allocations.
- HR weekly-off and holiday calendar management.
- HR usage reporting.
- Workflow-based approval with leave ledger and attendance override side effects.

## 5. Business Rules
- Leave is the canonical business record; workflow is the approval process. They are linked through `workflow.requests.entity_type = "leave.leave_request"`.
- Leave submission requires a current employee employment context, an active and effective policy, a policy rule for the requested leave type, and branch weekly-off configuration.
- Leave cannot span multiple leave years in the current implementation.
- Leave requests can require attachments depending on leave-type and policy-rule constraints.
- Leave overlap is blocked with `leave.overlap`.
- Balance checks are enforced unless the leave type allows negative balance.
- Workflow terminal hooks finalize the domain status and side effects in the same transaction.
- Approval writes ledger consumption rows and `attendance.day_overrides` entries with `ON_LEAVE` for countable days.
- Cancellation is only allowed for participant-owned pending requests.

## 6. User Journeys and Flows
- HR setup flow: create leave types -> create leave policies -> upsert policy rules -> assign employee policy -> allocate balance -> configure weekly off and holidays.
- Employee request flow: open `/leave` -> review balances -> submit request -> track workflow link -> optionally cancel while pending.
- Manager review flow: open team calendar for visibility -> approve or reject from Workflow Inbox.
- Approval flow: workflow approval triggers ledger consumption, attendance override writes, request status update, audit events, and notifications.
- Failure paths: missing policy, missing calendar configuration, insufficient balance, overlap, missing attachment, or workflow-definition absence.

## 7. Screen Inventory
- `/leave` - primary ESS leave screen for balances, request history, apply-leave sheet, cancel action, and workflow handoff.
- `/leave/team-calendar` - MSS monthly team leave calendar with depth toggle and selected-day side panel.
- Workflow Inbox / Request Detail - approval path for leave requests; the leave module depends on Workflow for decisioning.
- HR leave setup screens - Needs Verification. Backend support exists, but current frontend admin surfaces should be confirmed before documenting them as shipped routes.

## 8. UX/UI Specification
- `/leave` uses list-plus-right-panel patterns with balances, request history, and a sheet for request creation.
- Submit actions must disable while pending and surface validation or API errors through the shared toast/error UX.
- Scope-sensitive actions should fail closed when company and branch selection are missing.
- Team calendar should always show loading, empty, error, and selected-day detail states.
- Error copy should preserve correlation references via the shared error handling system.
- Responsive behavior should keep request actions and context links accessible without relying on desktop-only affordances.
- Accessibility should preserve semantic labels for leave type, dates, unit, half-day selection, attachment upload, and cancel confirmation.

## 9. Animations and Microinteractions
- Use existing sheet open/close transitions for the apply-leave action.
- Status chips should change deterministically after invalidation, not optimistic updates.
- Hover and focus behavior should remain aligned with the DS tables, filter bars, and calendar cells.
- Inline feedback should prefer explicit success toasts and field-level disabling over decorative motion.

## 10. Frontend Technical Notes
- Routes: `frontend/src/app/leave/page.tsx` and `frontend/src/app/leave/team-calendar/page.tsx`.
- API wrappers: `frontend/src/features/leave/api/leave.ts`.
- Query keys: `frontend/src/features/leave/queryKeys.ts`.
- The ESS page uses React Query for balances and infinite request pagination; the calendar page uses range-based query keys.
- Leave request submission also integrates with DMS file upload through `uploadFile()` when attachments are used.
- Workflow outbox invalidation is part of successful ESS submit/cancel flows.
- Current frontend admin leave setup screens are not yet verified; internal docs should avoid inventing routes that do not exist.

## 11. Backend Technical Notes
- Routers:
  - `backend/app/domains/leave/router_ess.py`
  - `backend/app/domains/leave/router_hr.py`
  - `backend/app/domains/leave/router_mss.py`
- Core business logic: `backend/app/domains/leave/service.py`
- Repository/data access: `backend/app/domains/leave/repo.py`
- Schemas: `backend/app/domains/leave/schemas.py`
- Permission helpers: `backend/app/domains/leave/policies.py`
- Workflow hook registration: `backend/app/domains/leave/__init__.py` and `backend/app/domains/leave/workflow_handler.py`
- Workflow hook behavior is deterministic and idempotent for approve, reject, and cancel transitions.

## 12. API Surface
- `GET /api/v1/leave/me/balances` - return balances for the selected year.
- `GET /api/v1/leave/me/requests` - return paginated ESS leave requests.
- `POST /api/v1/leave/me/requests` - submit a leave request.
- `POST /api/v1/leave/me/requests/{leave_request_id}/cancel` - cancel a pending leave request.
- `GET /api/v1/leave/types` - list leave types.
- `POST /api/v1/leave/types` - create a leave type.
- `GET /api/v1/leave/policies` - list leave policies.
- `POST /api/v1/leave/policies` - create a leave policy.
- `POST /api/v1/leave/policies/{policy_id}/rules` - upsert policy rules.
- `POST /api/v1/leave/employees/{employee_id}/policy` - assign a policy to an employee.
- `POST /api/v1/leave/allocations` - allocate leave balance.
- `GET /api/v1/leave/calendar/weekly-off` - read weekly off configuration.
- `PUT /api/v1/leave/calendar/weekly-off` - replace weekly off configuration.
- `GET /api/v1/leave/calendar/holidays` - list holidays.
- `POST /api/v1/leave/calendar/holidays` - create a holiday.
- `GET /api/v1/leave/reports/usage` - report leave usage.
- `GET /api/v1/leave/team/calendar` - return manager-visible team leave spans.
- Auth requirements: leave read/write permissions plus workflow approval permissions for approval actions.
- Error cases: `leave.policy.missing`, `leave.calendar.missing`, `leave.invalid_range`, `leave.type.not_found`, `leave.policy.rule.missing`, `leave.half_day.invalid`, `leave.attachment_required`, `leave.idempotency.conflict`, `leave.overlap`, `leave.insufficient_balance`, `leave.request.not_found`, `leave.request.not_pending`.

## 13. Data Model / DB Schema
- `leave.leave_types` - tenant-scoped leave type catalog.
- `leave.leave_policies` - effective-dated leave policy container.
- `leave.leave_policy_rules` - leave-type-specific rules within a policy.
- `leave.employee_leave_policy` - effective-dated employee policy assignment.
- `leave.leave_requests` - canonical leave request row linked to workflow.
- `leave.leave_request_days` - exploded day rows for overlap and attendance interactions.
- `leave.leave_ledger` - immutable balance ledger.
- `leave.weekly_off` - required branch calendar rows for weekdays 0..6.
- `leave.holidays` - tenant or branch holiday records.
- Related table: `attendance.day_overrides` receives `ON_LEAVE` rows on approval.
- Constraints and indexes should be verified from the Alembic history and the live leave tables; the legacy leave note has been retired.

## 14. Validations
- `year` on balances is bounded (`1970..2100`).
- Request cursor parsing must be valid timestamp plus UUID.
- `start_date` must be `<= end_date`.
- Half-day requests must be a single day and must include `half_day_part`.
- Leave type must exist and be active in the tenant.
- Requested leave must map to an active, effective employee policy and rule.
- Leave cannot span multiple leave years.
- Attachment file IDs must be valid and readable when attachments are supplied.
- Pending overlap and idempotency conflicts are enforced.
- Approval re-checks conflict-sensitive conditions such as balance and leave state.

## 15. Errors and Failure Scenarios
- Missing policy or calendar setup blocks submission with explicit leave codes.
- Overlap returns `leave.overlap`.
- Insufficient balance returns `leave.insufficient_balance`.
- Missing workflow link or non-pending request blocks cancellation.
- Team calendar rejects invalid ranges with `leave.invalid_range`.
- Participant-safe behavior applies where request ownership is required.
- Recovery guidance: configure weekly off, assign a policy, allocate balances, or complete workflow-definition setup.

## 16. Notifications and Audit Logs
- Workflow request creation notifies approvers through the shared workflow system.
- Approval and rejection paths generate audit entries via leave service hooks.
- Approval consumes ledger and finalizes request state with audit actions such as `leave.ledger.consume` and `leave.request.finalize`.
- Type, policy, policy-rule, assignment, allocation, weekly-off, and holiday changes are audited through leave service actions.
- Exact user-facing notification template inventory still needs verification.

## 17. Dependencies
- `Workflow` for approval, comments, notifications, and request visibility.
- `HRCore` for employee identity and current employment context.
- `TenancyOrganization` for branch and company scoping.
- `Attendance` for `attendance.day_overrides` side effects and leave-aware day calculations.
- `DMS` for attachment file validation and upload flows.

## 18. Limitations and Known Gaps
- Current frontend-admin leave setup screens are not yet fully verified in the web app.
- Customer-facing screenshots and flow assets are still missing from the module asset folders.
- Notification template details and support ownership need human confirmation.
- Regional leave-policy nuance beyond current v1 rules is outside the verified scope.

## 19. Testing Requirements
- Backend API coverage: `backend/tests/domains/leave/api/test_leave_management.py`.
- Frontend page coverage: `frontend/src/app/leave/__tests__/page.test.tsx`.
- Frontend manager calendar coverage: `frontend/src/app/leave/team-calendar/__tests__/page.test.tsx`.
- Integrated story coverage: `frontend/src/app/__tests__/m6.stories.test.tsx`.
- Critical regressions to retain:
  - submit leave successfully
  - overlap conflict
  - insufficient balance
  - workflow approval side effects
  - cancel pending request
  - team calendar range handling

## 20. Open Questions / TODO
- TODO: confirm the customer-facing route and copy for HR leave setup screens if they are promoted into the main web product.
- TODO: document the exact notification templates and recipients after support/product verification.
- TODO: add verified screenshots and flow diagrams into `docs/Modules/Leave/Assets/`.

## 21. References
- `backend/app/domains/leave/router_ess.py`
- `backend/app/domains/leave/router_hr.py`
- `backend/app/domains/leave/router_mss.py`
- `backend/app/domains/leave/service.py`
- `backend/app/domains/leave/repo.py`
- `backend/app/domains/leave/schemas.py`
- `backend/app/domains/leave/policies.py`
- `backend/app/domains/leave/workflow_handler.py`
- `frontend/src/app/leave/page.tsx`
- `frontend/src/app/leave/team-calendar/page.tsx`
- `frontend/src/features/leave/api/leave.ts`
- `frontend/src/features/leave/queryKeys.ts`
- `backend/tests/domains/leave/api/test_leave_management.py`
- `frontend/src/app/leave/__tests__/page.test.tsx`
- `frontend/src/app/leave/team-calendar/__tests__/page.test.tsx`
