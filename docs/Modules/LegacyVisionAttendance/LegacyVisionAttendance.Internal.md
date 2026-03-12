# LegacyVisionAttendance

    ## 1. Overview
    - Purpose: Legacy CCTV and vision-based attendance processing, jobs, results, artifacts, and related camera configuration.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **legacy**.

    ## 2. Scope
    - In scope: Camera setup, Video upload/finalize, Job control, Results and artifacts.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - Operations admin
- Security admin

    ## 4. Module Capabilities
    - Camera setup
- Video upload/finalize
- Job control
- Results and artifacts

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- TODO: module-specific rule inventory should be extended where current code or docs are fragmented.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete camera setup and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /dashboard - active route or known entry point.
- /setup - active route or known entry point.
- /cameras/[cameraId]/calibration - active route or known entry point.
- /videos - active route or known entry point.
- /jobs/[jobId] - active route or known entry point.
- /reports/[jobId] - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /dashboard, /setup, /cameras/[cameraId]/calibration, /videos, /jobs/[jobId], /reports/[jobId].
- Referenced frontend sources: frontend/src/app/dashboard/page.tsx, frontend/src/app/setup/page.tsx, frontend/src/app/videos/*, frontend/src/app/jobs/*, frontend/src/app/reports/*.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/api/v1/cameras.py, backend/app/api/v1/videos.py, backend/app/api/v1/jobs.py, backend/app/api/v1/results.py, app.face_system.api.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - GET /api/v1/branches/{branch_id}/cameras
- GET /api/v1/branches/{branch_id}/cameras/{camera_id}
- PUT /api/v1/branches/{branch_id}/cameras/{camera_id}/calibration
- PUT /api/v1/branches/{branch_id}/videos/{video_id}/file
- POST /api/v1/branches/{branch_id}/videos/{video_id}/finalize
- GET /api/v1/branches/{branch_id}/jobs/{job_id}
- POST /api/v1/branches/{branch_id}/jobs/{job_id}/cancel
- POST /api/v1/branches/{branch_id}/jobs/{job_id}/retry
- POST /api/v1/branches/{branch_id}/jobs/{job_id}/recompute
- GET /api/v1/branches/{branch_id}/jobs/{job_id}/events
- GET /api/v1/branches/{branch_id}/events/{event_id}/snapshot
- GET /api/v1/branches/{branch_id}/jobs/{job_id}/attendance
- GET /api/v1/branches/{branch_id}/jobs/{job_id}/metrics/hourly
- GET /api/v1/branches/{branch_id}/jobs/{job_id}/artifacts
- GET /api/v1/branches/{branch_id}/artifacts/{artifact_id}/download

    ## 13. Data Model / DB Schema
    - Legacy attendance and vision tables need consolidated verification.

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
    - TenancyOrganization

    ## 18. Limitations and Known Gaps
    - This surface predates the current HRMS module system and should not be positioned as the primary attendance product.
- Data-model inventory needs a dedicated follow-up if the legacy pipeline remains strategic.

    ## 19. Testing Requirements
    - Needs verification

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/dashboard/page.tsx
- frontend/src/app/setup/page.tsx
- frontend/src/app/videos/*
- frontend/src/app/jobs/*
- frontend/src/app/reports/*
- backend/app/api/v1/cameras.py
- backend/app/api/v1/videos.py
- backend/app/api/v1/jobs.py
- backend/app/api/v1/results.py
- app.face_system.api
- Needs verification
