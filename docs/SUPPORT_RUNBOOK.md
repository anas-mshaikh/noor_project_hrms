# Support Runbook

## Correlation reference workflow
- Ask the user for the error reference shown in the UI (`reference: <id>` or copied ref).
- Search backend and worker logs for that correlation id.
- Confirm the failing route, scope headers, and permission set before retrying anything.

## Common triage paths
### Login loop or unexpected sign-out
- Verify `/api/v1/auth/me` returns 200 for the current cookies.
- If it returns 401, re-authenticate.
- If it returns a scope error, clear selection and re-pick scope.

### Scope / forbidden loop
- Ask the user to use `Reset selection` from the error state or open `/scope` directly.
- Confirm the selected tenant/company/branch is still allowed for the user.
- Check for stale local storage or cookie mirrors (`noor_scope_*`).

### Missing payslip or document
- For ESS participant-safe views, a 404 does not prove the record does not exist.
- Verify the linked employee/account first.
- Search by employee and period/document id in the admin surface before escalating.

### Workflow request stuck pending
- Confirm the workflow definition is active.
- Check the request status in `/workflow/inbox` or `/workflow/requests/{id}`.
- Verify the approver has the correct permission and scope.

### Payroll publish/export issue
- Check payrun status and whether approval completed.
- `Publish` must only happen from `APPROVED`.
- For export issues, confirm the browser did not save a partial file and capture the correlation ref.

## Logs and commands
- Integration gate logs:
  - `docker compose logs --no-color`
- Backend only:
  - `cd backend && pytest -q`
  - `python3 backend/scripts/run_all_tests.py`
- Frontend only:
  - `cd frontend && npm run test`
  - `cd frontend && npm run build`

## Escalation notes
- Always include:
  - user role
  - selected scope
  - route
  - correlation reference
  - exact time of failure
- Do not ask users to share tokens, cookies, or secrets.
