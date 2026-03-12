# Testing Standards

## Backend

- Prefer pytest API and journey tests that simulate real client behavior.
- Use stable envelope assertions, permission checks, participant-safe behavior, and scope-fail-closed checks.
- Golden or end-to-end backend journeys should stay deterministic and marked explicitly.

## Frontend

- Prefer RTL + user-event + MSW for component and integration behavior.
- Use role-based queries, visible outcomes, and deterministic mocks.
- Keep Playwright smoke stable, role-based, and lightweight.

## Documentation verification

Before a module doc is considered complete:
- verify routes exist
- verify endpoints exist
- verify tests and known failure paths are referenced
- mark unknowns instead of inferring behavior

See also:
- `docs/CI_CD/CI_CD.md`
- `docs/CI_CD/CI_CD_BACKEND.md`
