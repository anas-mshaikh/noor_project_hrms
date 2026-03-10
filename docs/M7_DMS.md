# M7 DMS

## Routes
- `/settings/dms/doc-types` - tenant DMS document types catalog
- `/dms/employee-docs` - HR employee-scoped document browser
- `/dms/my-docs` - ESS document library
- `/dms/expiry` - HR upcoming expiry dashboard
- `/dms/documents/[docId]` - compatibility route for workflow notifications and direct links

## Permissions
- `dms:document-type:read`, `dms:document-type:write`
- `dms:document:read`, `dms:document:write`, `dms:document:verify`
- `dms:file:read`, `dms:file:write`
- `dms:expiry:read`, `dms:expiry:write`
- Workflow approvals continue to use `workflow:request:read` and `workflow:request:approve`

## Backend endpoints used
- `GET /api/v1/dms/document-types`
- `POST /api/v1/dms/document-types`
- `PATCH /api/v1/dms/document-types/{doc_type_id}`
- `GET /api/v1/hr/employees/{employee_id}/documents`
- `POST /api/v1/hr/employees/{employee_id}/documents`
- `POST /api/v1/dms/documents/{document_id}/versions`
- `POST /api/v1/dms/documents/{document_id}/verify-request`
- `GET /api/v1/ess/me/documents`
- `GET /api/v1/ess/me/documents/{document_id}`
- `GET /api/v1/dms/expiry/rules`
- `GET /api/v1/dms/expiry/upcoming?days=`
- `POST /api/v1/dms/files`
- `GET /api/v1/dms/files/{file_id}`
- `GET /api/v1/dms/files/{file_id}/download`

## Client V0 behavior
- HR DMS is employee-scoped. There is no global cross-employee document index in the current backend.
- Document detail shows the current version only. Replace flows upload a new current version; no version timeline is faked.
- ESS ships My Documents only. There is no ESS expiry dashboard in V0.
- Upload uses the existing `uploadFile()` / `apiForm()` path with disabled submit plus `Uploading...` state.
- Workflow request detail formats `DOCUMENT_VERIFICATION` payloads and links back into DMS.
- `/dms/documents/[docId]` prevents broken notification links and redirects to the best available DMS surface when it can resolve context.

## Test commands
- `cd frontend && npm run test`
- `cd frontend && npm run test:e2e -- --project=chromium`
- `docker compose up --build --abort-on-container-exit --exit-code-from frontend_tests frontend_tests`

## Known limitations
- Backend notifications currently link to `/dms/documents/{id}` without guaranteed employee context. The compatibility route handles this as best-effort only.
- Workflow payloads do not include the original filename, so workflow detail points users back to the DMS document view for the current file name.
- Expiry filtering is limited to horizon days because the backend upcoming endpoint does not support branch, type, or status filters.
