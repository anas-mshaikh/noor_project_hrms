# LegacyAdminImport

    ## 1. Overview
    - Purpose: Legacy branch-scoped monthly import pipeline for attendance summaries and publish flows.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **legacy**.

    ## 2. Scope
    - In scope: Dataset upload, Publish import, Monthly leaderboard.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - Operations admin

    ## 4. Module Capabilities
    - Dataset upload
- Publish import
- Monthly leaderboard

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- TODO: module-specific rule inventory should be extended where current code or docs are fragmented.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete dataset upload and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /admin/import - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /admin/import.
- Referenced frontend sources: frontend/src/app/admin/import/page.tsx.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/api/v1/imports.py.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - POST /api/v1/branches/{branch_id}/imports
- POST /api/v1/branches/{branch_id}/imports/{dataset_id}/publish
- GET /api/v1/branches/{branch_id}/months/{month_key}/leaderboard

    ## 13. Data Model / DB Schema
    - Import dataset tables need verification from code and migrations.

    ## 14. Validations
    - Field-level validations and scope checks should be copied from router schemas or service logic.
- Cross-field and business validations should be documented only when verified in code.
- TODO: add more specific validation inventory where current code has richer rule sets.

    ## 15. Errors and Failure Scenarios
    - Use stable module-specific error codes when available.
- Participant-safe read paths should avoid leaking resource existence.
- Preserve correlation references for support and QA workflows.

    ## 16. Notifications and Audit Logs
    - Document workflow or module notifications only when verified from code or existing docs.
- List audit actions and recipients where they are part of the module contract.
- TODO: notification inventory needs verification.

    ## 17. Dependencies
    - LegacyVisionAttendance

    ## 18. Limitations and Known Gaps
    - This is a transitional operations surface and should remain clearly tagged as legacy.
- Customer-facing guidance should be treated as operational-only until the long-term product direction is confirmed.

    ## 19. Testing Requirements
    - Needs verification

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/admin/import/page.tsx
- backend/app/api/v1/imports.py
- Needs verification
