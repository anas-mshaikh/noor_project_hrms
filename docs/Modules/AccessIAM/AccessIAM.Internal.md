# AccessIAM

    ## 1. Overview
    - Purpose: User, role, and permission administration for tenant-scoped access control.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **documented**.

    ## 2. Scope
    - In scope: User directory, User detail, Role assignment, Role catalog, Permission catalog.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - Tenant admin
- Security admin
- HR admin

    ## 4. Module Capabilities
    - User directory
- User detail
- Role assignment
- Role catalog
- Permission catalog

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- Current module behavior is documented from verified routes, services, and tests; unknowns are marked explicitly.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete user directory and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /settings/access/users - active route or known entry point.
- /settings/access/users/[userId] - active route or known entry point.
- /settings/access/roles - active route or known entry point.
- /settings/access/permissions - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /settings/access/users, /settings/access/users/[userId], /settings/access/roles, /settings/access/permissions.
- Referenced frontend sources: frontend/src/app/settings/access/*.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/domains/iam/router.py.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - POST /api/v1/users
- GET /api/v1/users
- GET/PATCH /api/v1/users/{user_id}
- POST/GET/DELETE /api/v1/users/{user_id}/roles
- GET /api/v1/roles
- GET /api/v1/permissions

    ## 13. Data Model / DB Schema
    - iam.users
- iam.roles
- iam.permissions
- iam.user_roles
- iam.role_permissions

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
- HRCore
- Workflow

    ## 18. Limitations and Known Gaps
    - Role model and default tenant role mapping need a cleaner customer explanation.
- No dedicated customer screenshots are currently available.

    ## 19. Testing Requirements
    - backend/tests/domains/iam/api/test_api_iam.py
- frontend/src/app/settings/access/users/__tests__/page.test.tsx
- frontend/src/app/settings/access/users/[userId]/__tests__/page.test.tsx
- frontend/src/app/settings/access/roles/__tests__/page.test.tsx
- frontend/src/app/settings/access/permissions/__tests__/page.test.tsx

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/settings/access/*
- backend/app/domains/iam/router.py
- backend/tests/domains/iam/api/test_api_iam.py
- frontend/src/app/settings/access/users/__tests__/page.test.tsx
- frontend/src/app/settings/access/users/[userId]/__tests__/page.test.tsx
- frontend/src/app/settings/access/roles/__tests__/page.test.tsx
- frontend/src/app/settings/access/permissions/__tests__/page.test.tsx
