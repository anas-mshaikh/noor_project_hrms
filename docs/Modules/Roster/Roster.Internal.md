# Roster

    ## 1. Overview
    - Purpose: Shift templates, branch default shifts, employee assignments, and per-day overrides.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **documented**.

    ## 2. Scope
    - In scope: Shift templates, Branch default shift, Employee assignments, Roster overrides.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - HR admin
- Roster admin

    ## 4. Module Capabilities
    - Shift templates
- Branch default shift
- Employee assignments
- Roster overrides

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- Current module behavior is documented from verified routes, services, and tests; unknowns are marked explicitly.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete shift templates and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /roster/shifts - active route or known entry point.
- /roster/default - active route or known entry point.
- /roster/assignments - active route or known entry point.
- /roster/overrides - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /roster/shifts, /roster/default, /roster/assignments, /roster/overrides.
- Referenced frontend sources: frontend/src/app/roster/*, frontend/src/features/roster/*.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/domains/roster/router.py and backend/app/domains/roster/service_*.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - POST/GET /api/v1/roster/branches/{branch_id}/shifts
- PATCH /api/v1/roster/shifts/{shift_template_id}
- PUT/GET /api/v1/roster/branches/{branch_id}/default-shift
- POST/GET /api/v1/roster/employees/{employee_id}/assignments
- PUT /api/v1/roster/employees/{employee_id}/overrides/{day}
- GET /api/v1/roster/employees/{employee_id}/overrides

    ## 13. Data Model / DB Schema
    - roster.shift_templates
- roster.branch_defaults
- roster.shift_assignments
- roster.roster_overrides

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
- TenancyOrganization
- Payables

    ## 18. Limitations and Known Gaps
    - Backend service file inventory should be linked more explicitly in a follow-up pass.
- No customer screenshots exist yet for assignment and override flows.

    ## 19. Testing Requirements
    - frontend/src/app/roster/shifts/__tests__/page.test.tsx
- frontend/src/app/roster/default/__tests__/page.test.tsx
- frontend/src/app/roster/assignments/__tests__/page.test.tsx
- frontend/src/app/roster/overrides/__tests__/page.test.tsx
- frontend/src/app/__tests__/m8.stories.test.tsx

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/roster/*
- frontend/src/features/roster/*
- backend/app/domains/roster/router.py
- backend/app/domains/roster/service_*
- frontend/src/app/roster/shifts/__tests__/page.test.tsx
- frontend/src/app/roster/default/__tests__/page.test.tsx
- frontend/src/app/roster/assignments/__tests__/page.test.tsx
- frontend/src/app/roster/overrides/__tests__/page.test.tsx
- frontend/src/app/__tests__/m8.stories.test.tsx
