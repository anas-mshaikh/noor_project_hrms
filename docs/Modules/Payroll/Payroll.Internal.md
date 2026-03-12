# Payroll

    ## 1. Overview
    - Purpose: Payroll setup, payrun generation, workflow approval, publishing, export, and ESS payslips.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **documented**.

    ## 2. Scope
    - In scope: Calendars and periods, Components, Salary structures, Employee compensation, Payruns, Approval, Publish, Export, ESS payslips.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - Payroll admin
- Approver
- Employee

    ## 4. Module Capabilities
    - Calendars and periods
- Components
- Salary structures
- Employee compensation
- Payruns
- Approval
- Publish
- Export
- ESS payslips

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- Current module behavior is documented from verified routes, services, and tests; unknowns are marked explicitly.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete calendars and periods and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /payroll - active route or known entry point.
- /payroll/calendars - active route or known entry point.
- /payroll/components - active route or known entry point.
- /payroll/structures - active route or known entry point.
- /payroll/structures/[structureId] - active route or known entry point.
- /payroll/compensation - active route or known entry point.
- /payroll/payruns - active route or known entry point.
- /payroll/payruns/[payrunId] - active route or known entry point.
- /ess/payslips - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /payroll, /payroll/calendars, /payroll/components, /payroll/structures, /payroll/structures/[structureId], /payroll/compensation, /payroll/payruns, /payroll/payruns/[payrunId], /ess/payslips.
- Referenced frontend sources: frontend/src/app/payroll/*, frontend/src/app/ess/payslips/page.tsx, frontend/src/features/payroll/*.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/domains/payroll/router_admin.py and backend/app/domains/payroll/router_ess.py.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - POST/GET /api/v1/payroll/calendars
- POST/GET /api/v1/payroll/calendars/{calendar_id}/periods
- POST/GET /api/v1/payroll/components
- POST /api/v1/payroll/salary-structures
- POST /api/v1/payroll/salary-structures/{structure_id}/lines
- GET /api/v1/payroll/salary-structures/{structure_id}
- POST/GET /api/v1/payroll/employees/{employee_id}/compensation
- POST /api/v1/payroll/payruns/generate
- GET /api/v1/payroll/payruns/{payrun_id}
- POST /api/v1/payroll/payruns/{payrun_id}/submit-approval
- POST /api/v1/payroll/payruns/{payrun_id}/publish
- GET /api/v1/payroll/payruns/{payrun_id}/export
- GET /api/v1/ess/me/payslips
- GET /api/v1/ess/me/payslips/{payslip_id}
- GET /api/v1/ess/me/payslips/{payslip_id}/download

    ## 13. Data Model / DB Schema
    - payroll.calendars
- payroll.periods
- payroll.components
- payroll.salary_structures
- payroll.salary_structure_lines
- payroll.employee_compensations
- payroll.payruns
- payroll.payrun_items
- payroll.payrun_item_lines
- payroll.payslips

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
    - Payables
- HRCore
- Workflow
- DMS
- TenancyOrganization

    ## 18. Limitations and Known Gaps
    - Payroll tax, compliance, and bank export behavior remain intentionally out of scope.
- Customer-facing payroll setup screenshots and rollout instructions need verification.

    ## 19. Testing Requirements
    - backend/tests/domains/payroll/api/test_payroll_v1.py
- frontend/src/app/payroll/__tests__/page.test.tsx
- frontend/src/app/payroll/calendars/__tests__/page.test.tsx
- frontend/src/app/payroll/components/__tests__/page.test.tsx
- frontend/src/app/payroll/structures/__tests__/page.test.tsx
- frontend/src/app/payroll/structures/[structureId]/__tests__/page.test.tsx
- frontend/src/app/payroll/compensation/__tests__/page.test.tsx
- frontend/src/app/payroll/payruns/__tests__/page.test.tsx
- frontend/src/app/payroll/payruns/[payrunId]/__tests__/page.test.tsx
- frontend/src/app/ess/payslips/__tests__/page.test.tsx
- frontend/src/app/__tests__/m9.stories.test.tsx

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/payroll/*
- frontend/src/app/ess/payslips/page.tsx
- frontend/src/features/payroll/*
- backend/app/domains/payroll/router_admin.py
- backend/app/domains/payroll/router_ess.py
- backend/tests/domains/payroll/api/test_payroll_v1.py
- frontend/src/app/payroll/__tests__/page.test.tsx
- frontend/src/app/payroll/calendars/__tests__/page.test.tsx
- frontend/src/app/payroll/components/__tests__/page.test.tsx
- frontend/src/app/payroll/structures/__tests__/page.test.tsx
- frontend/src/app/payroll/structures/[structureId]/__tests__/page.test.tsx
- frontend/src/app/payroll/compensation/__tests__/page.test.tsx
- frontend/src/app/payroll/payruns/__tests__/page.test.tsx
- frontend/src/app/payroll/payruns/[payrunId]/__tests__/page.test.tsx
- frontend/src/app/ess/payslips/__tests__/page.test.tsx
- frontend/src/app/__tests__/m9.stories.test.tsx
