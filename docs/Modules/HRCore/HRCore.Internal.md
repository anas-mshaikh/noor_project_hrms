# HRCore

    ## 1. Overview
    - Purpose: Employee directory, Employee 360, ESS profile, MSS team views, employment history, and employee-to-user linking.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **documented**.

    ## 2. Scope
    - In scope: Employee directory, Create employee, Employee 360, Employment records, Link user, ESS profile, MSS team.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - HR admin
- Employee
- Manager

    ## 4. Module Capabilities
    - Employee directory
- Create employee
- Employee 360
- Employment records
- Link user
- ESS profile
- MSS team

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- Current module behavior is documented from verified routes, services, and tests; unknowns are marked explicitly.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete employee directory and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /hr/employees - active route or known entry point.
- /hr/employees/[employeeId] - active route or known entry point.
- /ess/me - active route or known entry point.
- /mss/team - active route or known entry point.
- /mss/team/[employeeId] - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /hr/employees, /hr/employees/[employeeId], /ess/me, /mss/team, /mss/team/[employeeId].
- Referenced frontend sources: frontend/src/app/hr/employees/*, frontend/src/app/ess/me/page.tsx, frontend/src/app/mss/team/*.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/domains/hr_core/router_hr.py, backend/app/domains/hr_core/router_ess.py, backend/app/domains/hr_core/router_mss.py.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - POST/GET /api/v1/hr/employees
- GET/PATCH /api/v1/hr/employees/{employee_id}
- GET/POST /api/v1/hr/employees/{employee_id}/employment
- POST /api/v1/hr/employees/{employee_id}/link-user
- GET/PATCH /api/v1/ess/me/profile
- GET /api/v1/mss/team
- GET /api/v1/mss/team/{employee_id}

    ## 13. Data Model / DB Schema
    - hr_core.employees
- hr_core.persons
- hr_core.employee_employment
- hr_core.employee_user_links
- hr_core.employee_bank_accounts
- hr_core.employee_government_ids
- hr_core.employee_dependents

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
- AccessIAM
- Workflow
- DMS
- Payroll
- Roster
- Leave

    ## 18. Limitations and Known Gaps
    - Documents and payroll tabs in Employee 360 depend on other modules and need cross-module screenshots.
- Full field-by-field profile change ownership remains split with ProfileChange.

    ## 19. Testing Requirements
    - backend/tests/domains/hr_core/api/test_hr_core_hr.py
- backend/tests/domains/hr_core/api/test_hr_core_ess.py
- backend/tests/domains/hr_core/api/test_hr_core_mss.py
- frontend/src/app/hr/employees/__tests__/page.test.tsx
- frontend/src/app/hr/employees/[employeeId]/__tests__/page.test.tsx
- frontend/src/app/ess/me/__tests__/page.test.tsx
- frontend/src/app/mss/team/__tests__/page.test.tsx
- frontend/src/app/mss/team/[employeeId]/__tests__/page.test.tsx

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/hr/employees/*
- frontend/src/app/ess/me/page.tsx
- frontend/src/app/mss/team/*
- backend/app/domains/hr_core/router_hr.py
- backend/app/domains/hr_core/router_ess.py
- backend/app/domains/hr_core/router_mss.py
- backend/tests/domains/hr_core/api/test_hr_core_hr.py
- backend/tests/domains/hr_core/api/test_hr_core_ess.py
- backend/tests/domains/hr_core/api/test_hr_core_mss.py
- frontend/src/app/hr/employees/__tests__/page.test.tsx
- frontend/src/app/hr/employees/[employeeId]/__tests__/page.test.tsx
- frontend/src/app/ess/me/__tests__/page.test.tsx
- frontend/src/app/mss/team/__tests__/page.test.tsx
- frontend/src/app/mss/team/[employeeId]/__tests__/page.test.tsx
