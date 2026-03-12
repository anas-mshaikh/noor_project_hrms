# WorkTasks

    ## 1. Overview
    - Purpose: Branch work-task assignment and assignment-read APIs with a frontend shell that needs more verification.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **partial**.

    ## 2. Scope
    - In scope: Task list, Assignment lookup, Auto-assignment job support.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - Operations manager
- Supervisor

    ## 4. Module Capabilities
    - Task list
- Assignment lookup
- Auto-assignment job support

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- TODO: module-specific rule inventory should be extended where current code or docs are fragmented.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete task list and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /tasks - active route or known entry point.
- /tasks/team - active route or known entry point.
- /tasks/approvals - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /tasks, /tasks/team, /tasks/approvals.
- Referenced frontend sources: frontend/src/app/tasks/*.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/api/v1/tasks.py, backend/app/work/service.py, backend/app/work/tasks.py.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - GET /api/v1/branches/{branch_id}/tasks
- GET /api/v1/branches/{branch_id}/tasks/{task_id}/assignments

    ## 13. Data Model / DB Schema
    - work.tasks
- work.task_assignments
- work.task_assignment_events

    ## 14. Validations
    - Field-level validations and scope checks should be copied from router schemas or service logic.
- Cross-field and business validations should be documented only when verified in code.
- TODO: add more specific validation inventory where current code has richer rule sets.

    ## 15. Errors and Failure Scenarios
    - Use stable module-specific error codes when available.
- Participant-safe read paths should avoid leaking resource existence.
- Preserve correlation references for support and QA workflows.

    ## 16. Notifications and Audit Logs
    - Document workflow or module notifications only when verified from code or existing docs.
- List audit actions and recipients where they are part of the module contract.
- TODO: notification inventory needs verification.

    ## 17. Dependencies
    - TenancyOrganization

    ## 18. Limitations and Known Gaps
    - Frontend and backend capabilities are not fully aligned in current docs.
- Permissions and customer guidance need verification before this module is treated as active.

    ## 19. Testing Requirements
    - Needs verification

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/tasks/*
- backend/app/api/v1/tasks.py
- backend/app/work/service.py
- backend/app/work/tasks.py
- Needs verification
