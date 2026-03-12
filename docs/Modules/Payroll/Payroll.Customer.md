# Payroll Guide

    ## 1. What this module does
    Payroll setup, payrun generation, workflow approval, publishing, export, and ESS payslips.

    ## 2. Who can use it
    - Payroll admin
- Approver
- Employee

    ## 3. Permissions overview
    - payroll:calendar:read
- payroll:calendar:write
- payroll:component:read
- payroll:component:write
- payroll:structure:read
- payroll:structure:write
- payroll:compensation:read
- payroll:compensation:write
- payroll:payrun:read
- payroll:payrun:generate
- payroll:payrun:approve
- payroll:payrun:publish
- payroll:payslip:read

    ## 4. Setup / configuration
    - Create calendars and periods.
- Create components and salary structures.
- Assign employee compensation.
- Verify payables and workflow definitions before generating payruns.

    ## 5. How to use it
    - Use the main Payroll workflow from the verified route set: /payroll, /payroll/calendars, /payroll/components, /payroll/structures, /payroll/structures/[structureId], /payroll/compensation, /payroll/payruns, /payroll/payruns/[payrunId], /ess/payslips.
- Review prerequisite setup and permissions before using the module in production.
- Escalate with the correlation reference if the module returns an error or a workflow stalls.

    ## 6. Key screens explained
    - /payroll
- /payroll/calendars
- /payroll/components
- /payroll/structures
- /payroll/structures/[structureId]
- /payroll/compensation
- /payroll/payruns
- /payroll/payruns/[payrunId]
- /ess/payslips

    ## 7. Common tasks
    - Calendars and periods
- Components
- Salary structures
- Employee compensation
- Payruns
- Approval
- Publish
- Export
- ESS payslips

    ## 8. Best practices
    - Use the correct company and branch scope before acting.
- Verify permissions before assuming a missing button or page is a defect.
- Keep workflow-driven actions inside the module flow; do not bypass approval surfaces.

    ## 9. Troubleshooting
    - Confirm that you are signed in with the correct role and scope.
    - Check whether a prerequisite setup step is missing.
    - If an action fails, capture the correlation reference and escalate through the support process.
    - Use the support runbooks under `docs/CI_CD/` and include the correlation reference when escalating API or workflow issues.

    ## 10. FAQ
    - Q: Why can a page show Access denied? A: The module is permission-gated and backend authorization remains authoritative.
- Q: Why do some reads return a neutral not-found message? A: Participant-safe behavior avoids leaking another employee's data.
- Q: What should I send to support? A: The correlation reference from the error state or API response.

    ## 11. Limitations users should know
    - Payroll tax, compliance, and bank export behavior remain intentionally out of scope.
- Customer-facing payroll setup screenshots and rollout instructions need verification.

    ## 12. Support / escalation notes
    - Primary engineering reference: `docs/Modules/Payroll/Payroll.Internal.md`
    - Shared runbooks: `docs/CI_CD/SUPPORT_RUNBOOK.md` and `docs/CI_CD/BACKEND_SUPPORT_RUNBOOK.md`
    - Include the correlation reference, affected route, user role, and scope when escalating.
