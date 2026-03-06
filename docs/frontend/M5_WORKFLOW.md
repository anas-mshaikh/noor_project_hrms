# M5 — Workflow Backbone (Frontend)

Milestone 5 ships the workflow backbone UI in the Noor HRMS web app (`frontend/`).

Goals:
- Inbox + Outbox workbenches backed by real workflow APIs (no ad-hoc fetch mocks)
- Request Detail workbench with actions + comments + attachments
- Workflow Definitions builder (admin) for creating + step configuration + activation
- Deterministic, production-like tests (Vitest + RTL + MSW) + a minimal Playwright smoke (mocked)

Non-goals:
- No new backend endpoints or schema changes
- No “All statuses” inbox (backend v1 supports pending only)
- No definition update / deactivate (backend v1 is create + steps replace + activate only)

## Navigation

Workflow lives under the existing “Inbox” module in the top bar (previously hidden).

- Top bar module label: **Workflow**
- Sidebar items:
  - `/workflow/inbox` (Inbox)
  - `/workflow/outbox` (Outbox)
- Old `/inbox/*` messaging placeholders remain hidden (`v0Hidden: true`)

Implementation: `frontend/src/config/navigation.ts`

## Routes

- `/workflow/inbox`
- `/workflow/outbox`
- `/workflow/requests/[requestId]` (deep-link workbench; used by backend notifications)

Settings (admin console):
- `/settings/workflow` (redirects to definitions)
- `/settings/workflow/definitions`
- `/settings/workflow/definitions/[definitionId]`

## Permissions (frontend gating)

Workflow:
- View (inbox/outbox/detail): `workflow:request:read` OR `workflow:request:admin`
- Approve/Reject actions: `workflow:request:approve`
- Cancel action: backend enforces requester-or-admin rules; UI shows cancel when:
  - `workflow:request:admin` OR `created_by_user_id === me.user.id`

DMS (attachments):
- Read metadata + download + attach: `dms:file:read`
- Upload: `dms:file:write` (upload is disabled unless both read + write are present)

Settings / definitions:
- Read: `workflow:definition:read`
- Write: `workflow:definition:write`

Note: permission gating is a UX convenience; backend remains authoritative.

## Backend Endpoints Used

Workflow (`/api/v1/workflow/*`):
- `GET  /workflow/inbox` (cursor pagination via `next_cursor`)
- `GET  /workflow/outbox` (cursor pagination via `next_cursor`)
- `GET  /workflow/requests/{request_id}`
- `POST /workflow/requests/{request_id}/approve`
- `POST /workflow/requests/{request_id}/reject`
- `POST /workflow/requests/{request_id}/cancel`
- `POST /workflow/requests/{request_id}/comments`
- `POST /workflow/requests/{request_id}/attachments`
- `GET  /workflow/definitions`
- `POST /workflow/definitions`
- `POST /workflow/definitions/{definition_id}/steps` (replace all steps; sequential indices required)
- `POST /workflow/definitions/{definition_id}/activate`

DMS (`/api/v1/dms/*`):
- `POST /dms/files` (multipart upload)
- `GET  /dms/files/{file_id}` (metadata)
- `GET  /dms/files/{file_id}/download` (bytes; downloaded via `apiDownload`)

## Frontend Architecture

Data layer (pure API wrappers + query keys):
- `frontend/src/features/workflow/api/workflow.ts`
- `frontend/src/features/workflow/queryKeys.ts`
- `frontend/src/features/dms/api/files.ts`
- `frontend/src/features/dms/queryKeys.ts`

Shared request workbench UI:
- `frontend/src/features/workflow/components/WorkflowRequestDetailCard.tsx`
- `frontend/src/features/workflow/components/WorkflowRequestContextPanel.tsx`

Error handling:
- All requests flow through `frontend/src/lib/api.ts` (ApiError normalization + correlation ids)
- Friendly copy mapping in `frontend/src/lib/errorUx.ts` (includes workflow codes)

## UX Details / Constraints

Inbox:
- Backend v1 supports “pending only”. UI exposes:
  - `Pending`
  - `All (v1 not supported)` disabled option
- Pagination is cursor-based: UI uses **Load more**
- Selection is persisted in the URL search param `?id=<uuid>` (refresh-safe)

Outbox:
- Cursor pagination with **Load more**
- Status filter maps to backend query param values (pending/approved/rejected/canceled/draft)
- Cancel is available only for `PENDING` rows

Request detail:
- Actions are disabled when status != `PENDING`
- Comments and attachments live in the right context column
- Attachments: upload (DMS) -> attach (workflow) -> download (DMS)

Definitions builder:
- Create definition (basic fields)
- Edit steps in detail page (replace-all)
- Activate definition (no deactivate in v1)

## Testing

Unit + component tests:
- `cd frontend && npm run test`

E2E smoke (mocked):
- `cd frontend && npm run test:e2e`

MSW handlers live under the enterprise test kit:
- `frontend/src/test/msw/handlers/workflow.handlers.ts`
- `frontend/src/test/msw/handlers/dms.handlers.ts`

Representative component tests:
- Inbox: `frontend/src/app/workflow/inbox/__tests__/page.test.tsx`
- Outbox: `frontend/src/app/workflow/outbox/__tests__/page.test.tsx`
- Deep-link detail (comments + attachments): `frontend/src/app/workflow/requests/[requestId]/__tests__/page.test.tsx`
- Definitions list: `frontend/src/app/settings/workflow/definitions/__tests__/page.test.tsx`
- Definitions editor: `frontend/src/app/settings/workflow/definitions/[definitionId]/__tests__/page.test.tsx`

