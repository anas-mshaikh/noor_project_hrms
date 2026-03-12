# M9 — Payroll

## Scope
M9 adds the payroll setup, payrun operations, workflow approval handoff, publish/export, and ESS payslips surfaces on top of the existing backend APIs.

## Routes
### HR
- `/payroll`
- `/payroll/calendars`
- `/payroll/components`
- `/payroll/structures`
- `/payroll/structures/[structureId]`
- `/payroll/compensation`
- `/payroll/payruns`
- `/payroll/payruns/[payrunId]`

### Self Service
- `/ess/payslips`

## Backend endpoints used
### Setup
- `GET /api/v1/payroll/calendars`
- `POST /api/v1/payroll/calendars`
- `GET /api/v1/payroll/calendars/{calendarId}/periods?year=`
- `POST /api/v1/payroll/calendars/{calendarId}/periods`
- `GET /api/v1/payroll/components?type=`
- `POST /api/v1/payroll/components`
- `POST /api/v1/payroll/salary-structures`
- `GET /api/v1/payroll/salary-structures/{structureId}`
- `POST /api/v1/payroll/salary-structures/{structureId}/lines`
- `GET /api/v1/payroll/employees/{employeeId}/compensation`
- `POST /api/v1/payroll/employees/{employeeId}/compensation`

### Payruns
- `POST /api/v1/payroll/payruns/generate`
- `GET /api/v1/payroll/payruns/{payrunId}?include_lines=1`
- `POST /api/v1/payroll/payruns/{payrunId}/submit-approval`
- `POST /api/v1/payroll/payruns/{payrunId}/publish`
- `GET /api/v1/payroll/payruns/{payrunId}/export?format=csv`

### ESS payslips
- `GET /api/v1/ess/me/payslips?year=`
- `GET /api/v1/ess/me/payslips/{payslipId}`
- `GET /api/v1/ess/me/payslips/{payslipId}/download`

### Workflow integration
- existing workflow read/approve/reject endpoints for `PAYRUN_APPROVAL`

### Supporting endpoints
- `GET /api/v1/hr/employees`
- `GET /api/v1/hr/employees/{employeeId}`

## Permissions
### Payroll admin
- `payroll:calendar:read`
- `payroll:calendar:write`
- `payroll:component:read`
- `payroll:component:write`
- `payroll:structure:read`
- `payroll:structure:write`
- `payroll:compensation:read`
- `payroll:compensation:write`
- `payroll:payrun:read`
- `payroll:payrun:generate`
- `payroll:payrun:submit`
- `payroll:payrun:publish`
- `payroll:payrun:export`

### ESS
- `payroll:payslip:read`

### Workflow
- `workflow:request:read`
- `workflow:request:approve`

## Scope rules
- `/payroll/*` stays inside the HR module.
- Payroll setup surfaces are tenant-scoped.
- Compensation is employee-scoped and requires an active company selection.
- Payrun generation is branch-scoped and fails closed without active company + branch scope.
- `/ess/payslips` stays under Self Service and is actor-scoped.

## UX notes
- Payroll Home is a checklist entrypoint because the backend does not expose a dashboard summary endpoint.
- Structures and payruns do not have browse/list endpoints in v1, so the UI uses create + open-by-ID flows instead of fake tables.
- Compensation is additive/create-only in v1; the UI exposes "Add compensation record" and overlap conflicts fail closed.
- Payrun totals are always backend-derived; there is no optimistic payroll math.
- Payrun approval is handled only through Workflow. The payrun detail links to the workflow request, and Workflow links back to the payrun.
- Workflow cancel is hidden for payrun approvals because the backend cancel hook is a no-op for payroll.
- ESS payslips are JSON downloads in v1. The web app does not invent a PDF viewer.

## Known limits
- No payrun list endpoint exists.
- No salary structure list endpoint exists.
- No global compensation list exists.
- Components, structures, periods, and compensation are additive/create-only unless the backend already exposes a read/detail route.
- No period auto-generation endpoint exists.
- Export is CSV only through the backend export endpoint.

## Tests
### Frontend unit + component
```bash
cd /Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend
npm run test
```

### Build/type gate
```bash
cd /Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend
npm run build
```

### Playwright smoke
```bash
cd /Users/anasshaikh/Documents/Work/noor_project_HRMS/attendence_system/frontend
npm run test:e2e -- --project=chromium
```

## Golden flows covered
1. Create payroll calendar and period.
2. Create component.
3. Create structure and add lines.
4. Add employee compensation.
5. Generate payrun.
6. Submit payrun for workflow approval.
7. Approve payrun in Workflow.
8. Publish payrun.
9. Open ESS payslips and download the published payslip.
