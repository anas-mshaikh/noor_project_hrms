# Recruitment Guide

    ## 1. What this module does
    Hiring openings, resumes, screening runs, ATS application actions, and hiring pipeline surfaces.

    ## 2. Who can use it
    - Recruiter
- HR admin
- Hiring manager

    ## 3. Permissions overview
    - hr:recruiting:read
- hr:recruiting:write

    ## 4. Setup / configuration
    - Verify your role permissions.
- Confirm company and branch scope where the module requires it.
- Review related workflow or setup prerequisites before starting operational use.

    ## 5. How to use it
    - Use the main Recruitment workflow from the verified route set: /hr, /hr/openings, /hr/openings/[id], /hr/openings/new, /hr/runs, /hr/pipeline.
- Review prerequisite setup and permissions before using the module in production.
- Escalate with the correlation reference if the module returns an error or a workflow stalls.

    ## 6. Key screens explained
    - /hr
- /hr/openings
- /hr/openings/[id]
- /hr/openings/new
- /hr/runs
- /hr/pipeline

    ## 7. Common tasks
    - Openings
- Resume upload and parsing
- Screening runs
- ATS application review
- Pipeline

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
    - Recruitment UI and ATS surface need a full verified screen audit.
- Customer-facing setup guidance for local parsing and embedding pipelines needs verification.

    ## 12. Support / escalation notes
    - Primary engineering reference: `docs/Modules/Recruitment/Recruitment.Internal.md`
    - Shared runbooks: `docs/CI_CD/SUPPORT_RUNBOOK.md` and `docs/CI_CD/BACKEND_SUPPORT_RUNBOOK.md`
    - Include the correlation reference, affected route, user role, and scope when escalating.
