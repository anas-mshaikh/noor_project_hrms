# Payables

    ## 1. Overview
    - Purpose: Payroll-ready payable-day summaries for employee, team, and admin reporting plus controlled recomputation.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **documented**.

    ## 2. Scope
    - In scope: My payable days, Team payable days, Admin payable days, Recompute.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - Employee
- Manager
- Payroll admin

    ## 4. Module Capabilities
    - My payable days
- Team payable days
- Admin payable days
- Recompute

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- Current module behavior is documented from verified routes, services, and tests; unknowns are marked explicitly.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete my payable days and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /payables/me - active route or known entry point.
- /payables/team - active route or known entry point.
- /payables/admin - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /payables/me, /payables/team, /payables/admin.
- Referenced frontend sources: frontend/src/app/payables/*, frontend/src/features/payables/*.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/domains/attendance/router_ess.py, backend/app/domains/attendance/router_mss.py, and backend/app/domains/attendance/router_admin.py.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - GET /api/v1/attendance/me/payable-days
- GET /api/v1/attendance/team/payable-days
- GET /api/v1/attendance/admin/payable-days
- POST /api/v1/attendance/payable/recompute

    ## 13. Data Model / DB Schema
    - attendance.payable_day_summaries

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
    - Attendance
- Roster
- Leave
- HRCore
- Payroll

    ## 18. Limitations and Known Gaps
    - Long-range reporting/export behavior beyond current APIs is not available.
- Customer wording for manager depth filters should be reviewed.

    ## 19. Testing Requirements
    - backend/tests/domains/attendance/api/test_payable_summaries.py
- frontend/src/app/payables/me/__tests__/page.test.tsx
- frontend/src/app/payables/team/__tests__/page.test.tsx
- frontend/src/app/payables/admin/__tests__/page.test.tsx
- frontend/src/app/__tests__/m8.stories.test.tsx

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/payables/*
- frontend/src/features/payables/*
- backend/app/domains/attendance/router_ess.py
- backend/app/domains/attendance/router_mss.py
- backend/app/domains/attendance/router_admin.py
- backend/tests/domains/attendance/api/test_payable_summaries.py
- frontend/src/app/payables/me/__tests__/page.test.tsx
- frontend/src/app/payables/team/__tests__/page.test.tsx
- frontend/src/app/payables/admin/__tests__/page.test.tsx
- frontend/src/app/__tests__/m8.stories.test.tsx
