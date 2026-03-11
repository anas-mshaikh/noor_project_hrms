# RBAC Matrix

This matrix is the frontend routing and action-view baseline. Backend permission checks remain authoritative.

| Area | Route / Action | Minimum permission(s) |
| --- | --- | --- |
| Workflow | `/workflow/inbox` | `workflow:request:read` or `workflow:request:admin` |
| Workflow | approve/reject | `workflow:request:approve` |
| ESS | `/attendance/*` | `attendance:punch:read`, `attendance:correction:read` |
| ESS | `/leave` | `leave:balance:read` or `leave:request:read` |
| ESS | `/dms/my-docs` | `dms:document:read` |
| ESS | `/ess/payslips` | `payroll:payslip:read` |
| HR | `/hr/employees` | `hr:employee:read` |
| HR | `/roster/*` | corresponding `roster:*` read/write permissions |
| HR | `/payables/admin` | `attendance:payable:admin:read` |
| HR | `/dms/employee-docs` | `dms:document:read` |
| HR | verify DMS doc | `dms:document:verify` |
| HR | `/payroll/*` | corresponding `payroll:*` read/write/generate/submit/publish/export permissions |
| Settings | `/settings/access` | `iam:user:read`, `iam:user:write`, `iam:role:assign`, `iam:permission:read` |
| Settings | `/settings/workflow` | `workflow:definition:read` or `workflow:definition:write` |
| Settings | `/settings/dms` | `dms:document-type:read` or `dms:document-type:write` |

## Notes
- Hidden v0 placeholder modules must not remain reachable through visible navigation.
- Participant-safe ESS screens should prefer neutral not-found copy over existence leakage.
- If a route is unauthorized, render an explicit forbidden state instead of crashing.
