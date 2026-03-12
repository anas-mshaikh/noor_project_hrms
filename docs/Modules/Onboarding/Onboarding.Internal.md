# Onboarding

    ## 1. Overview
    - Purpose: Plan templates, template tasks, employee bundles, ESS submissions, DMS-backed document tasks, and onboarding packet submission.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **documented**.

    ## 2. Scope
    - In scope: Plan templates, Template tasks, Employee bundles, ESS document/form/ack tasks, Submit packet to profile change.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - HR admin
- Employee

    ## 4. Module Capabilities
    - Plan templates
- Template tasks
- Employee bundles
- ESS document/form/ack tasks
- Submit packet to profile change

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- Current module behavior is documented from verified routes, services, and tests; unknowns are marked explicitly.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete plan templates and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /hr/onboarding - active route or known entry point.
- /hr/onboarding/[employeeId] - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /hr/onboarding, /hr/onboarding/[employeeId].
- Referenced frontend sources: frontend/src/app/hr/onboarding/page.tsx and frontend/src/app/hr/onboarding/[employeeId]/page.tsx.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/domains/onboarding/router_hr.py, backend/app/domains/onboarding/router_ess.py.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - GET/POST /api/v1/onboarding/plan-templates
- POST /api/v1/onboarding/plan-templates/{template_id}/tasks
- POST /api/v1/onboarding/employees/{employee_id}/bundle
- GET /api/v1/onboarding/employees/{employee_id}/bundle
- GET /api/v1/ess/me/onboarding
- POST /api/v1/ess/me/onboarding/tasks/{task_id}/submit-form
- POST /api/v1/ess/me/onboarding/tasks/{task_id}/upload-document
- POST /api/v1/ess/me/onboarding/tasks/{task_id}/ack
- POST /api/v1/ess/me/onboarding/bundle/{bundle_id}/submit-packet

    ## 13. Data Model / DB Schema
    - onboarding.plan_templates
- onboarding.plan_template_tasks
- onboarding.employee_bundles
- onboarding.employee_tasks

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
- DMS
- Workflow
- ProfileChange

    ## 18. Limitations and Known Gaps
    - Current `/hr/onboarding` frontend is UI-only mock data and does not yet represent the live backend behavior end to end.
- Customer screenshots and real ESS onboarding pages need verification.

    ## 19. Testing Requirements
    - backend/tests/domains/onboarding/api/test_onboarding_templates_bundles.py
- backend/tests/domains/onboarding/e2e/test_onboarding_packet_submit_flow.py

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/hr/onboarding/page.tsx
- frontend/src/app/hr/onboarding/[employeeId]/page.tsx
- backend/app/domains/onboarding/router_hr.py
- backend/app/domains/onboarding/router_ess.py
- backend/tests/domains/onboarding/api/test_onboarding_templates_bundles.py
- backend/tests/domains/onboarding/e2e/test_onboarding_packet_submit_flow.py
