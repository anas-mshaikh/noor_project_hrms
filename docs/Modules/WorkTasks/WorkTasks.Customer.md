# WorkTasks Guide

    ## 1. What this module does
    Branch work-task assignment and assignment-read APIs with a frontend shell that needs more verification.

    ## 2. Who can use it
    - Operations manager
- Supervisor

    ## 3. Permissions overview
    - Needs verification

    ## 4. Setup / configuration
    - Verify your role permissions.
- Confirm company and branch scope where the module requires it.
- Review related workflow or setup prerequisites before starting operational use.

    ## 5. How to use it
    - Use the main WorkTasks workflow from the verified route set: /tasks, /tasks/team, /tasks/approvals.
- Review prerequisite setup and permissions before using the module in production.
- Escalate with the correlation reference if the module returns an error or a workflow stalls.

    ## 6. Key screens explained
    - /tasks
- /tasks/team
- /tasks/approvals

    ## 7. Common tasks
    - Task list
- Assignment lookup
- Auto-assignment job support

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
    - Frontend and backend capabilities are not fully aligned in current docs.
- Permissions and customer guidance need verification before this module is treated as active.

    ## 12. Support / escalation notes
    - Primary engineering reference: `docs/Modules/WorkTasks/WorkTasks.Internal.md`
    - Shared runbooks: `docs/CI_CD/SUPPORT_RUNBOOK.md` and `docs/CI_CD/BACKEND_SUPPORT_RUNBOOK.md`
    - Include the correlation reference, affected route, user role, and scope when escalating.
