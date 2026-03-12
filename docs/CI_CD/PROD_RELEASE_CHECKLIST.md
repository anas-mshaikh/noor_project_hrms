# Production Release Checklist

## Before cutting a release
- Confirm the target commit is merged to `main`.
- Confirm required checks are green:
  - PR CI
  - Integration CI
  - E2E Smoke if the release touches golden flows
- Verify there are no open rollback blockers in `docs/ROLLBACK.md`.

## Release-candidate validation
- Run `./scripts/rc-check.sh` from repo root.
- If the release changes user journeys, also run `RUN_E2E=1 ./scripts/rc-check.sh`.
- Review `docs/RBAC_MATRIX.md` for any permission changes in the release.

## Staging validation
- Sign in as HR/Admin and validate:
  - scope selection
  - workflow inbox approve/reject
  - employee directory create/link flow
  - leave/apply + attendance correction
  - DMS open/download/verify
  - payroll generate -> submit approval -> publish -> export
- Sign in as employee and validate:
  - ESS profile
  - leave request visibility
  - DMS my docs
  - payslip list/download
- Record any correlation references from failures in the release notes.

## Cut the release
- Run the GitHub `Release Bundle` workflow with the target version label.
- Review the generated `RELEASE_NOTES.md` artifact.
- Create or confirm the deployment change ticket.
- Announce the release window and rollback owner.

## After deployment
- Smoke `/login`, `/scope`, `/workflow/inbox`, `/attendance/punch`, `/leave`, `/dms/employee-docs`, `/payroll/payruns`, and `/ess/payslips`.
- Watch application logs and support channel for correlation references.
- Mark the release complete only after core flows are stable.
