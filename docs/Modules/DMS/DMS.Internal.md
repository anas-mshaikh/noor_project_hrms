# DMS

    ## 1. Overview
    - Purpose: Document types, files, employee document library, verification workflows, and expiry monitoring.
    - Business value: provides a verified module-level reference for engineering, product, design, QA, and support.
    - Summary: current documentation status is **documented**.

    ## 2. Scope
    - In scope: Document types, File upload/download, Employee documents, Document versions, Verification workflow, Expiry rules, Upcoming expiry reporting, ESS my documents.
    - Out of scope: unverified behavior, future roadmap items, and unsupported flows not present in code or existing docs.

    ## 3. Personas and Roles
    - HR admin
- Verifier
- Employee

    ## 4. Module Capabilities
    - Document types
- File upload/download
- Employee documents
- Document versions
- Verification workflow
- Expiry rules
- Upcoming expiry reporting
- ESS my documents

    ## 5. Business Rules
    - Tenant, company, and branch scope must fail closed where applicable.
- Backend authorization remains authoritative even when the frontend hides or disables actions.
- Current module behavior is documented from verified routes, services, and tests; unknowns are marked explicitly.

    ## 6. User Journeys and Flows
    - Primary workflow: use the module to complete document types and related follow-up actions.
- Alternate path: handle missing prerequisite, forbidden, and participant-safe deny cases.
- Failure path: surface stable error code, correlation ID, and recovery guidance.

    ## 7. Screen Inventory
    - /dms/employee-docs - active route or known entry point.
- /dms/expiry - active route or known entry point.
- /dms/my-docs - active route or known entry point.
- /dms/documents/[docId] - active route or known entry point.
- /settings/dms/doc-types - active route or known entry point.

    ## 8. UX/UI Specification
    - Use DS templates and explicit loading, empty, error, and forbidden states.
- Keep customer-facing actions scoped to the relevant company or branch when applicable.
- Respect RTL, keyboard access, and current shell/navigation conventions.

    ## 9. Animations and Microinteractions
    - Follow shared DS hover, focus, sheet, and panel interaction patterns.
    - Keep motion secondary to state clarity, especially for tables, drawers, and approval actions.
    - Use inline validation and deterministic success feedback instead of decorative motion.

    ## 10. Frontend Technical Notes
    - Frontend entry points: /dms/employee-docs, /dms/expiry, /dms/my-docs, /dms/documents/[docId], /settings/dms/doc-types.
- Referenced frontend sources: frontend/src/app/dms/*, frontend/src/app/settings/dms/doc-types/page.tsx, and frontend/src/features/dms/*.
- State and data fetching should remain aligned with feature-first API wrappers and query-key patterns.

    ## 11. Backend Technical Notes
    - Referenced backend sources: backend/app/domains/dms/router_document_types.py, backend/app/domains/dms/router_files.py, backend/app/domains/dms/router_documents.py, backend/app/domains/dms/router_hr.py, backend/app/domains/dms/router_ess.py, backend/app/domains/dms/router_expiry.py.
- Authorization and scope enforcement happen server-side and should be described from the router and service layer.
- Background jobs or hooks should be documented when they alter externally visible module behavior.

    ## 12. API Surface
    - GET/POST/PATCH /api/v1/dms/document-types
- POST /api/v1/dms/files
- GET /api/v1/dms/files/{file_id}
- GET /api/v1/dms/files/{file_id}/download
- POST /api/v1/dms/documents/{document_id}/versions
- POST /api/v1/dms/documents/{document_id}/verify-request
- POST /api/v1/hr/employees/{employee_id}/documents
- GET /api/v1/hr/employees/{employee_id}/documents
- GET /api/v1/ess/me/documents
- GET /api/v1/ess/me/documents/{document_id}
- GET/POST /api/v1/dms/expiry/rules
- GET /api/v1/dms/expiry/upcoming

    ## 13. Data Model / DB Schema
    - dms.files
- dms.document_types
- dms.documents
- dms.document_versions
- dms.document_links
- dms.expiry_rules
- dms.expiry_events

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
    - Workflow
- HRCore
- Onboarding
- Payroll

    ## 18. Limitations and Known Gaps
    - Customer-ready screenshots for expiry management and compatibility routes are missing.
- Version history beyond current supported surfaces should be treated carefully to avoid overstating functionality.

    ## 19. Testing Requirements
    - backend/tests/domains/dms/api/test_dms_documents.py
- frontend/src/app/dms/employee-docs/__tests__/page.test.tsx
- frontend/src/app/dms/my-docs/__tests__/page.test.tsx
- frontend/src/app/dms/expiry/__tests__/page.test.tsx
- frontend/src/app/dms/documents/[docId]/__tests__/page.test.tsx
- frontend/src/app/settings/dms/doc-types/__tests__/page.test.tsx

    ## 20. Open Questions / TODO
    - TODO: confirm customer-approved terminology and screenshots.
    - TODO: verify support ownership and escalation contacts for this module.
    - TODO: extend feature-level docs only where the master doc becomes too dense.

    ## 21. References
    - frontend/src/app/dms/*
- frontend/src/app/settings/dms/doc-types/page.tsx
- backend/app/domains/dms/router_document_types.py
- backend/app/domains/dms/router_files.py
- backend/app/domains/dms/router_documents.py
- backend/app/domains/dms/router_hr.py
- backend/app/domains/dms/router_ess.py
- backend/app/domains/dms/router_expiry.py
- backend/tests/domains/dms/api/test_dms_documents.py
- frontend/src/app/dms/employee-docs/__tests__/page.test.tsx
- frontend/src/app/dms/my-docs/__tests__/page.test.tsx
- frontend/src/app/dms/expiry/__tests__/page.test.tsx
- frontend/src/app/dms/documents/[docId]/__tests__/page.test.tsx
- frontend/src/app/settings/dms/doc-types/__tests__/page.test.tsx
