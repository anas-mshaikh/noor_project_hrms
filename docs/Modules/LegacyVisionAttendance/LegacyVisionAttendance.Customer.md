# LegacyVisionAttendance Guide

    ## 1. What this module does
    Legacy CCTV and vision-based attendance processing, jobs, results, artifacts, and related camera configuration.

    ## 2. Who can use it
    - Operations admin
- Security admin

    ## 3. Permissions overview
    - vision:camera:write
- vision:video:upload
- vision:job:run
- vision:results:read

    ## 4. Setup / configuration
    - Verify your role permissions.
- Confirm company and branch scope where the module requires it.
- Review related workflow or setup prerequisites before starting operational use.

    ## 5. How to use it
    - Use the main LegacyVisionAttendance workflow from the verified route set: /dashboard, /setup, /cameras/[cameraId]/calibration, /videos, /jobs/[jobId], /reports/[jobId].
- Review prerequisite setup and permissions before using the module in production.
- Escalate with the correlation reference if the module returns an error or a workflow stalls.

    ## 6. Key screens explained
    - /dashboard
- /setup
- /cameras/[cameraId]/calibration
- /videos
- /jobs/[jobId]
- /reports/[jobId]

    ## 7. Common tasks
    - Camera setup
- Video upload/finalize
- Job control
- Results and artifacts

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
    - This surface predates the current HRMS module system and should not be positioned as the primary attendance product.
- Data-model inventory needs a dedicated follow-up if the legacy pipeline remains strategic.

    ## 12. Support / escalation notes
    - Primary engineering reference: `docs/Modules/LegacyVisionAttendance/LegacyVisionAttendance.Internal.md`
    - Shared runbooks: `docs/CI_CD/SUPPORT_RUNBOOK.md` and `docs/CI_CD/BACKEND_SUPPORT_RUNBOOK.md`
    - Include the correlation reference, affected route, user role, and scope when escalating.
