# Attendance

    ## 1. Overview
    - Purpose: Attendance days, punch flows, correction requests, admin correction listing, and the leave-aware effective attendance model.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **documented**.

    ## 2. Scope
    - In scope: Attendance days, Punch in/out, Punch settings, Corrections, Admin corrections reporting.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - Employee
- Manager
- Attendance admin

    ## 4. Module Capabilities
    - Attendance days
- Punch in/out
- Punch settings
- Corrections
- Admin corrections reporting

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- Current module behavior is documented from verified routes, services, and tests; unknowns are marked explicitly.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete attendance days and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /attendance/days - active route or known entry point.
- /attendance/punch - active route or known entry point.
- /attendance/corrections - active route or known entry point.
- /attendance/corrections/new - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /attendance/days, /attendance/punch, /attendance/corrections, /attendance/corrections/new.
- Referenced frontend sources: frontend/src/app/attendance/* and frontend/src/features/attendance/*.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/domains/attendance/router_ess.py, backend/app/domains/attendance/router_admin.py, backend/app/domains/attendance/router_mss.py.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - GET /api/v1/attendance/me/days
- POST /api/v1/attendance/me/punch-in
- POST /api/v1/attendance/me/punch-out
- GET /api/v1/attendance/me/punch-state
- POST /api/v1/attendance/me/corrections
- GET /api/v1/attendance/me/corrections
- POST /api/v1/attendance/me/corrections/{correction_id}/cancel
- GET /api/v1/attendance/corrections
- GET/PUT /api/v1/attendance/punch-settings

    ## 13. Data Model / DB Schema
    - attendance.attendance_daily
- attendance.day_overrides
- attendance.attendance_corrections
- attendance.punch_settings
- attendance.punches
- attendance.work_sessions

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
    - HRCore
- Leave
- Workflow
- TenancyOrganization

    ## 18. Limitations and Known Gaps
    - Legacy CCTV and import attendance remain in the repo and need careful separation from the modern attendance module narrative.
- Some admin and manager views need additional screenshots or verified customer wording.

    ## 19. Testing Requirements
    - backend/tests/domains/attendance/api/test_attendance_punching.py
- backend/tests/domains/attendance/api/test_attendance_regularization.py
- frontend/src/app/attendance/days/__tests__/page.test.tsx
- frontend/src/app/attendance/punch/__tests__/page.test.tsx
- frontend/src/app/attendance/corrections/__tests__/page.test.tsx
- frontend/src/app/attendance/corrections/new/__tests__/page.test.tsx

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/attendance/*
- backend/app/domains/attendance/router_ess.py
- backend/app/domains/attendance/router_admin.py
- backend/app/domains/attendance/router_mss.py
- backend/tests/domains/attendance/api/test_attendance_punching.py
- backend/tests/domains/attendance/api/test_attendance_regularization.py
- frontend/src/app/attendance/days/__tests__/page.test.tsx
- frontend/src/app/attendance/punch/__tests__/page.test.tsx
- frontend/src/app/attendance/corrections/__tests__/page.test.tsx
- frontend/src/app/attendance/corrections/new/__tests__/page.test.tsx
