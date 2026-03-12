# Leave Guide

## 1. What this module does
The Leave module lets HR configure leave programs, employees request leave, managers review team leave visibility, and workflow approvals update balances and attendance consistently.

## 2. Who can use it
- Employees use it to view balances, request leave, and cancel pending requests.
- Managers use it to view team leave spans and approve requests through Workflow.
- HR admins use it to configure leave types, policies, allocations, and branch calendars.

## 3. Permissions overview
- Employee actions rely on leave request and balance permissions.
- Team calendar visibility relies on manager/team leave permissions.
- Setup actions rely on leave type, policy, allocation, and admin read/write permissions.
- Approvals happen through Workflow permissions rather than a separate leave approval screen.

## 4. Setup / configuration
- Create leave types for the tenant.
- Create at least one active leave policy.
- Add policy rules for each supported leave type.
- Assign a policy to each employee who will request leave.
- Allocate balances where the leave type requires balance checking.
- Configure weekly off and holidays for the branch.
- Ensure an active `LEAVE_REQUEST` workflow definition exists.

## 5. How to use it
- Employee request flow: open `/leave`, review balances, submit the leave request, and track the request status.
- Employee cancel flow: open the request history and cancel a request while it is still pending.
- Manager calendar flow: open `/leave/team-calendar`, review approved leave spans, then use Workflow Inbox to act on pending requests.
- HR setup flow: configure leave types, policies, assignments, and calendars before rollout.

## 6. Key screens explained
- `/leave` - balances, request history, leave request sheet, and workflow handoff.
- `/leave/team-calendar` - monthly team calendar for approved leave spans.
- Workflow Inbox - approval and rejection actions for leave requests.
- HR setup screens - Needs Verification. Backend support exists, but the exact customer-facing admin routes should be confirmed.

## 7. Common tasks
- Check annual or sick leave balance.
- Submit a full-day or half-day leave request.
- Attach evidence when a leave type requires it.
- Cancel a pending request.
- Review who is on leave in the team calendar.
- Configure leave policy and allocation for a new employee.

## 8. Best practices
- Configure weekly off and holidays before opening leave requests to employees.
- Make sure every employee has an active leave policy assignment.
- Keep leave-type rules aligned with real HR policy before allocating balances.
- Use Workflow Inbox for approval decisions; do not try to bypass the workflow path.

## 9. Troubleshooting
- If the Apply Leave button is disabled, confirm the user has permission and the correct company/branch scope is selected.
- If submission fails, check whether the employee has a leave policy, balance, and branch calendar setup.
- If a request cannot be canceled, it is usually already terminal or missing its workflow link.
- If the page shows an error, record the correlation reference and escalate with the request date, leave type, and user role.

## 10. FAQ
- Q: Why can an employee see balances but still fail to submit? A: Submission also requires policy rules, calendar setup, and sufficient balance checks.
- Q: Why does the manager calendar not show pending requests? A: It is designed to show approved leave spans; approvals happen in Workflow Inbox.
- Q: Why does the system block a second request for the same dates? A: Overlap protection prevents duplicate or conflicting leave requests.

## 11. Limitations users should know
- HR setup screens in the current web app need final verification before they are used as the customer-facing source of truth.
- Notification wording and screenshots are still being finalized.
- Advanced policy simulation and regional compliance rules are not documented as supported behavior.

## 12. Support / escalation notes
- Internal engineering reference: `docs/Modules/Leave/Leave.Internal.md`
- Shared support runbooks: `docs/CI_CD/SUPPORT_RUNBOOK.md` and `docs/CI_CD/BACKEND_SUPPORT_RUNBOOK.md`
- Always include the correlation reference, leave type, request dates, employee, and scope when escalating.
