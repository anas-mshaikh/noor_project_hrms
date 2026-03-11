# Rollback

## Trigger conditions
- Required golden flow fails in production.
- Support receives repeated correlation references for the same release.
- A release gate was bypassed or produced a false green.

## Immediate steps
- Pause further deployments.
- Identify the release version and deployment timestamp.
- Capture failing correlation references and affected routes.
- Revert to the last known good deployment artifact or commit.

## Validation after rollback
- Re-run `/login`, `/scope`, `/workflow/inbox`, `/attendance/punch`, `/leave`, `/dms/my-docs`, `/payroll/payruns`, `/ess/payslips`.
- Confirm CI was green on the restored commit.
- Document the failure mode in the release notes and support runbook.
