# Recruitment

    ## 1. Overview
    - Purpose: Hiring openings, resumes, screening runs, ATS application actions, and hiring pipeline surfaces.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **documented**.

    ## 2. Scope
    - In scope: Openings, Resume upload and parsing, Screening runs, ATS application review, Pipeline.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - Recruiter
- HR admin
- Hiring manager

    ## 4. Module Capabilities
    - Openings
- Resume upload and parsing
- Screening runs
- ATS application review
- Pipeline

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- Current module behavior is documented from verified routes, services, and tests; unknowns are marked explicitly.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete openings and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /hr - active route or known entry point.
- /hr/openings - active route or known entry point.
- /hr/openings/[id] - active route or known entry point.
- /hr/openings/new - active route or known entry point.
- /hr/runs - active route or known entry point.
- /hr/pipeline - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /hr, /hr/openings, /hr/openings/[id], /hr/openings/new, /hr/runs, /hr/pipeline.
- Referenced frontend sources: frontend/src/app/hr/page.tsx, frontend/src/app/hr/openings/*, frontend/src/app/hr/runs/*, frontend/src/app/hr/pipeline/page.tsx.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/api/v1/openings.py, backend/app/api/v1/screening_runs.py, backend/app/api/v1/ats.py.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - GET/PATCH /api/v1/branches/{branch_id}/openings/{opening_id}
- GET /api/v1/branches/{branch_id}/openings
- GET /api/v1/branches/{branch_id}/openings/{opening_id}/resumes
- GET /api/v1/branches/{branch_id}/resumes/{resume_id}/views
- POST /api/v1/branches/{branch_id}/openings/{opening_id}/search
- GET /api/v1/branches/{branch_id}/screening-runs/{run_id}
- POST /api/v1/branches/{branch_id}/screening-runs/{run_id}/cancel
- GET /api/v1/branches/{branch_id}/screening-runs/{run_id}/results
- GET /api/v1/branches/{branch_id}/openings/{opening_id}/applications
- PATCH /api/v1/branches/{branch_id}/applications/{application_id}
- POST /api/v1/branches/{branch_id}/applications/{application_id}/reject
- POST /api/v1/branches/{branch_id}/applications/{application_id}/hire
- GET /api/v1/branches/{branch_id}/applications/{application_id}/notes

    ## 13. Data Model / DB Schema
    - hr.openings
- hr.resumes
- hr.screening_runs
- hr.screening_results
- hr.applications
- hr_application_notes

    ## 14. Validations
    - Field-level validations and scope checks should be copied from router schemas or service logic.
- Cross-field and business validations should be documented only when verified in code.
- Known validation behavior is captured from verified code paths and tests.

    ## 15. Errors and Failure Scenarios
    - Use stable module-specific error codes when available.
- Participant-safe read paths should avoid leaking resource existence.
- Preserve correlation references for support and QA workflows.

    ## 16. Notifications and Audit Logs
    - Document workflow or module notifications only when verified from code or existing docs.
- List audit actions and recipients where they are part of the module contract.
- Known notifications are summarized from current workflow and service behavior.

    ## 17. Dependencies
    - TenancyOrganization
- Workflow
- Notes
- LegacyVisionAttendance

    ## 18. Limitations and Known Gaps
    - Recruitment UI and ATS surface need a full verified screen audit.
- Customer-facing setup guidance for local parsing and embedding pipelines needs verification.

    ## 19. Testing Requirements
    - TODO: recruitment-specific frontend and backend test coverage should be inventoried in a follow-up pass.

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/hr/page.tsx
- frontend/src/app/hr/openings/*
- frontend/src/app/hr/runs/*
- frontend/src/app/hr/pipeline/page.tsx
- backend/app/api/v1/openings.py
- backend/app/api/v1/screening_runs.py
- backend/app/api/v1/ats.py
- TODO: recruitment-specific frontend and backend test coverage should be inventoried in a follow-up pass.
