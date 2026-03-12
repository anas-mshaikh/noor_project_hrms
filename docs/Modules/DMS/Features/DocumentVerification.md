# Document Verification

This feature supplements `docs/Modules/DMS/DMS.Internal.md`.

## Overview
Document verification routes DMS documents through Workflow for approval or rejection.

## Purpose
Make employee document verification auditable and reusable across DMS, onboarding, and payroll-linked surfaces.

## Rules
- Verification is workflow-driven.
- HR/admin or workflow participants can access the relevant document context.
- ESS access remains participant-safe.

## Flows
- HR uploads or versions a document
- HR requests verification
- Approver acts in Workflow
- Document status and downstream links update

## Screens
- `/dms/employee-docs`
- `/workflow/inbox`
- `/workflow/requests/[requestId]`

## Backend/API notes
- `POST /api/v1/dms/documents/{document_id}/verify-request`
- workflow approval and rejection endpoints

## DB notes
- `dms.documents`
- `dms.document_versions`
- `workflow.requests`

## Edge cases
- already terminal workflow
- unresolved compatibility route
- participant-safe deny on ESS reads

## Errors
- `dms.document.verify.already_terminal`
- `dms.document.not_found`
- `payroll.payslip.not_found` for linked payslip contexts when applicable

## Tests
- `backend/tests/domains/dms/api/test_dms_documents.py`
- `frontend/src/app/dms/employee-docs/__tests__/page.test.tsx`
- `frontend/src/app/workflow/requests/[requestId]/__tests__/page.test.tsx`

## Open questions
- Confirm the final customer terminology for verifier personas.
