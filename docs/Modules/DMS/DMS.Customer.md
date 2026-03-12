# DMS Guide

    ## 1. What this module does
    Document types, files, employee document library, verification workflows, and expiry monitoring.

    ## 2. Who can use it
    - HR admin
- Verifier
- Employee

    ## 3. Permissions overview
    - dms:file:read
- dms:file:write
- dms:document-type:read
- dms:document-type:write
- dms:document:read
- dms:document:write
- dms:document:verify
- dms:expiry:read
- dms:expiry:write

    ## 4. Setup / configuration
    - Create document types.
- Set access permissions for HR and verifiers.
- Confirm expiry rules and document verification workflow definitions if verification is required.

    ## 5. How to use it
    - Use the main DMS workflow from the verified route set: /dms/employee-docs, /dms/expiry, /dms/my-docs, /dms/documents/[docId], /settings/dms/doc-types.
- Review prerequisite setup and permissions before using the module in production.
- Escalate with the correlation reference if the module returns an error or a workflow stalls.

    ## 6. Key screens explained
    - /dms/employee-docs
- /dms/expiry
- /dms/my-docs
- /dms/documents/[docId]
- /settings/dms/doc-types

    ## 7. Common tasks
    - Document types
- File upload/download
- Employee documents
- Document versions
- Verification workflow
- Expiry rules
- Upcoming expiry reporting
- ESS my documents

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
    - Customer-ready screenshots for expiry management and compatibility routes are missing.
- Version history beyond current supported surfaces should be treated carefully to avoid overstating functionality.

    ## 12. Support / escalation notes
    - Primary engineering reference: `docs/Modules/DMS/DMS.Internal.md`
    - Shared runbooks: `docs/CI_CD/SUPPORT_RUNBOOK.md` and `docs/CI_CD/BACKEND_SUPPORT_RUNBOOK.md`
    - Include the correlation reference, affected route, user role, and scope when escalating.
