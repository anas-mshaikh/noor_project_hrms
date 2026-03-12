# TenancyOrganization

    ## 1. Overview
    - Purpose: Tenant bootstrap, scope selection, companies, branches, org units, grades, job titles, and org chart management.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **documented**.

    ## 2. Scope
    - In scope: Bootstrap, Scope selection, Company management, Branch management, Org units, Org chart, Grades and job titles.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - Platform admin
- Tenant admin
- HR admin

    ## 4. Module Capabilities
    - Bootstrap
- Scope selection
- Company management
- Branch management
- Org units
- Org chart
- Grades and job titles

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- Current module behavior is documented from verified routes, services, and tests; unknowns are marked explicitly.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete bootstrap and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /setup - active route or known entry point.
- /scope - active route or known entry point.
- /settings/org/companies - active route or known entry point.
- /settings/org/branches - active route or known entry point.
- /settings/org/org-units - active route or known entry point.
- /settings/org/org-chart - active route or known entry point.
- /settings/org/job-titles - active route or known entry point.
- /settings/org/grades - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /setup, /scope, /settings/org/companies, /settings/org/branches, /settings/org/org-units, /settings/org/org-chart, /settings/org/job-titles, /settings/org/grades.
- Referenced frontend sources: frontend/src/app/setup/page.tsx, frontend/src/app/scope/page.tsx, frontend/src/app/settings/org/*.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/domains/tenancy/router.py.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - POST /api/v1/bootstrap
- GET/POST /api/v1/tenancy/companies
- GET/POST /api/v1/tenancy/branches
- GET/POST /api/v1/tenancy/org-units
- GET /api/v1/tenancy/org-chart
- GET/POST /api/v1/tenancy/job-titles
- GET/POST /api/v1/tenancy/grades

    ## 13. Data Model / DB Schema
    - tenancy.tenants
- tenancy.companies
- tenancy.branches
- tenancy.org_units
- tenancy.job_titles
- tenancy.grades

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
    - AccessIAM
- HRCore
- Workflow

    ## 18. Limitations and Known Gaps
    - Exact customer-facing onboarding for bootstrap ownership needs verification.
- Support ownership for multi-tenant bootstrap flows is not documented in code.

    ## 19. Testing Requirements
    - backend/tests/domains/tenancy/api/test_api_bootstrap.py
- backend/tests/domains/tenancy/api/test_api_tenancy.py
- frontend/src/app/setup/__tests__/page.test.tsx
- frontend/src/app/settings/org/*/__tests__

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/setup/page.tsx
- frontend/src/app/scope/page.tsx
- frontend/src/app/settings/org/*
- backend/app/domains/tenancy/router.py
- backend/tests/domains/tenancy/api/test_api_bootstrap.py
- backend/tests/domains/tenancy/api/test_api_tenancy.py
- frontend/src/app/setup/__tests__/page.test.tsx
- frontend/src/app/settings/org/*/__tests__
