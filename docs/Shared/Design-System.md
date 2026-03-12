# Design System and UX Conventions

## Shared UI rules

- Use existing DS components and templates rather than inventing one-off layouts.
- Every primary page should define loading, empty, error, and forbidden states.
- Use `PageHeader`, `DataTable`, `EmptyState`, `ErrorState`, `DSCard`, `RightPanelStack`, and the current template set where applicable.
- Preserve RTL and locale-aware behavior.
- Keep forms keyboard-accessible and use semantic controls.

## Interaction rules

- Disable submit actions while a mutation is pending.
- Prefer explicit confirmation or deterministic status feedback for workflow and data-changing actions.
- Surface correlation IDs in user-visible error states when available.
- Prefer scoped, contextual feedback over global noise.

## Motion and microinteractions

- Use the existing design-system conventions for hover, focus, and sheet/dialog transitions.
- Do not add decorative motion that obscures workflow state or table readability.
- Keep microinteractions purposeful: row selection, status change, inline validation, and retry flows.
