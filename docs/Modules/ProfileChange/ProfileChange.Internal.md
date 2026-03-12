# ProfileChange

    ## 1. Overview
    - Purpose: Controlled employee profile change requests approved through workflow and applied deterministically to HR core records.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **documented**.

    ## 2. Scope
    - In scope: ESS profile change request submit, Request listing, Cancel request, Workflow approval and apply hook.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - Employee
- Approver
- HR admin

    ## 4. Module Capabilities
    - ESS profile change request submit
- Request listing
- Cancel request
- Workflow approval and apply hook

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- Current module behavior is documented from verified routes, services, and tests; unknowns are marked explicitly.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete ess profile change request submit and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - No standalone dedicated frontend page verified; appears through ESS/profile flows, onboarding packet flows, and workflow detail. - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: No standalone dedicated frontend page verified; appears through ESS/profile flows, onboarding packet flows, and workflow detail..
- Referenced frontend sources: Workflow detail and related ESS profile flows; explicit route still needs verification..
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/domains/profile_change/router_ess.py, backend/app/domains/profile_change/router_hr.py, backend/app/domains/profile_change/*.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - POST /api/v1/ess/me/profile-change-requests
- GET /api/v1/ess/me/profile-change-requests
- POST /api/v1/ess/me/profile-change-requests/{request_id}/cancel
- GET /api/v1/hr/profile-change-requests

    ## 13. Data Model / DB Schema
    - hr_core.profile_change_requests
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
    - HRCore
- Workflow
- Onboarding

    ## 18. Limitations and Known Gaps
    - Standalone frontend screens are not yet clearly verified from the repo.
- Customer guidance should be confirmed against the actual ESS entry point.

    ## 19. Testing Requirements
    - backend/tests/domains/profile_change/e2e/test_profile_change_workflow_apply.py
- backend/tests/domains/profile_change/unit/test_change_set_validation.py

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - Workflow detail and related ESS profile flows; explicit route still needs verification.
- backend/app/domains/profile_change/router_ess.py
- backend/app/domains/profile_change/router_hr.py
- backend/app/domains/profile_change/*
- backend/tests/domains/profile_change/e2e/test_profile_change_workflow_apply.py
- backend/tests/domains/profile_change/unit/test_change_set_validation.py
