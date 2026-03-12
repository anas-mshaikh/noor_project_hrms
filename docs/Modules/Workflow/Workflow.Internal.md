# Workflow

    ## 1. Overview
    - Purpose: Shared approval backbone for request definitions, inbox and outbox, request detail, comments, attachments, and domain hooks.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **documented**.

    ## 2. Scope
    - In scope: Inbox, Outbox, Request detail, Approve/reject/cancel, Comments, Attachments, Definition builder.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - Requester
- Approver
- Workflow admin

    ## 4. Module Capabilities
    - Inbox
- Outbox
- Request detail
- Approve/reject/cancel
- Comments
- Attachments
- Definition builder

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- Current module behavior is documented from verified routes, services, and tests; unknowns are marked explicitly.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete inbox and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /workflow/inbox - active route or known entry point.
- /workflow/outbox - active route or known entry point.
- /workflow/requests/[requestId] - active route or known entry point.
- /settings/workflow/definitions - active route or known entry point.
- /settings/workflow/definitions/[definitionId] - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /workflow/inbox, /workflow/outbox, /workflow/requests/[requestId], /settings/workflow/definitions, /settings/workflow/definitions/[definitionId].
- Referenced frontend sources: frontend/src/app/workflow/* and frontend/src/app/settings/workflow/*.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/domains/workflow/router.py, backend/app/domains/workflow/service.py.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - POST /api/v1/workflow/requests
- GET /api/v1/workflow/requests/{request_id}
- GET /api/v1/workflow/inbox
- GET /api/v1/workflow/outbox
- POST /api/v1/workflow/requests/{request_id}/cancel
- POST /api/v1/workflow/requests/{request_id}/approve
- POST /api/v1/workflow/requests/{request_id}/reject
- POST /api/v1/workflow/requests/{request_id}/comments
- POST /api/v1/workflow/requests/{request_id}/attachments
- GET/POST /api/v1/workflow/definitions
- POST /api/v1/workflow/definitions/{definition_id}/steps
- POST /api/v1/workflow/definitions/{definition_id}/activate

    ## 13. Data Model / DB Schema
    - workflow.request_types
- workflow.requests
- workflow.request_comments
- workflow.request_attachments
- workflow.definitions
- workflow.definition_steps
- workflow.notification_outbox
- workflow.notifications

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
- Notifications
- DMS
- Leave
- Attendance
- ProfileChange
- Onboarding
- Payroll

    ## 18. Limitations and Known Gaps
    - Cross-module workflow definition governance is not fully documented.
- Notification ownership and escalation rules need human confirmation.

    ## 19. Testing Requirements
    - backend/tests/domains/workflow/api/test_workflow_engine.py
- frontend/src/app/workflow/inbox/__tests__/page.test.tsx
- frontend/src/app/workflow/outbox/__tests__/page.test.tsx
- frontend/src/app/workflow/requests/[requestId]/__tests__/page.test.tsx
- frontend/src/app/settings/workflow/definitions/__tests__/page.test.tsx
- frontend/src/app/settings/workflow/definitions/[definitionId]/__tests__/page.test.tsx

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/workflow/*
- frontend/src/app/settings/workflow/*
- backend/app/domains/workflow/router.py
- backend/app/domains/workflow/service.py
- backend/tests/domains/workflow/api/test_workflow_engine.py
- frontend/src/app/workflow/inbox/__tests__/page.test.tsx
- frontend/src/app/workflow/outbox/__tests__/page.test.tsx
- frontend/src/app/workflow/requests/[requestId]/__tests__/page.test.tsx
- frontend/src/app/settings/workflow/definitions/__tests__/page.test.tsx
- frontend/src/app/settings/workflow/definitions/[definitionId]/__tests__/page.test.tsx
