# LegacyAdminImport Guide

    ## 1. What this module does
    Legacy branch-scoped monthly import pipeline for attendance summaries and publish flows.

    ## 2. Who can use it
    - Operations admin

    ## 3. Permissions overview
    - imports:write

    ## 4. Setup / configuration
    - Verify your role permissions.
- Confirm company and branch scope where the module requires it.
- Review related workflow or setup prerequisites before starting operational use.

    ## 5. How to use it
    - Use the main LegacyAdminImport workflow from the verified route set: /admin/import.
- Review prerequisite setup and permissions before using the module in production.
- Escalate with the correlation reference if the module returns an error or a workflow stalls.

    ## 6. Key screens explained
    - /admin/import

    ## 7. Common tasks
    - Dataset upload
- Publish import
- Monthly leaderboard

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
    - This is a transitional operations surface and should remain clearly tagged as legacy.
- Customer-facing guidance should be treated as operational-only until the long-term product direction is confirmed.

    ## 12. Support / escalation notes
    - Primary engineering reference: `docs/Modules/LegacyAdminImport/LegacyAdminImport.Internal.md`
    - Shared runbooks: `docs/CI_CD/SUPPORT_RUNBOOK.md` and `docs/CI_CD/BACKEND_SUPPORT_RUNBOOK.md`
    - Include the correlation reference, affected route, user role, and scope when escalating.
