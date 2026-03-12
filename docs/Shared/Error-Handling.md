# Error Handling

## Backend rules

- Domain errors use stable codes through `AppError` and the exception handlers.
- Error payloads should surface a stable `code`, human-readable `message`, optional `details`, and the correlation ID when available.
- Scope failures must fail closed and use stable codes rather than ambiguous generic messages.

## Frontend rules

- Requests normalize through `ApiError` and module-specific error mappings.
- Pages should use explicit `ErrorState` components for route-level failures.
- Mutations should use inline validation, field messaging, or toasts depending on the interaction pattern.
- Participant-safe deny behavior must not leak whether another employee's resource exists.

## Known patterns

- Use guided empty or setup states for missing prerequisites.
- Use explicit forbidden states when the user lacks permission.
- Preserve correlation IDs in user-visible error surfaces for support escalation.
