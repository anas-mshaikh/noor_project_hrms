# Contributing to Documentation

## Core rules

- Organize documentation by business module first.
- Each module must have one internal master doc and one customer guide.
- Shared rules belong in `docs/Shared/`; do not duplicate them inside modules unless a module-specific exception exists.
- Feature docs are supplemental only and must link back to the module master doc.
- Use `TODO`, `Unknown`, or `Needs Verification` instead of guessing.
- Keep headings stable. Internal docs must use the standard 21-section structure. Customer docs must use the standard 12-section structure.

## File and folder conventions

- Use the existing lowercase `docs/` root.
- Use PascalCase for module folders and file names.
- Use these canonical names per module:
  - `<ModuleName>.Internal.md`
  - `<ModuleName>.Customer.md`
  - `CHANGELOG.md`
- Keep feature docs under `docs/Modules/<ModuleName>/Features/`.
- Keep screen and flow assets under `docs/Modules/<ModuleName>/Assets/`.

## What belongs in shared docs

Place platform-wide guidance in `docs/Shared/` when it applies across multiple modules, such as:
- API envelopes and error handling
- RBAC conventions
- audit logging patterns
- notification conventions
- testing standards
- design-system rules

## What belongs in module docs

Keep module-specific truth inside the module folder:
- business rules
- flows
- screens
- validations
- endpoints
- schema details
- tests
- module-specific limitations

## Migration workflow

1. Read the old doc and the code paths it references.
2. Move verified information into the new module doc.
3. Mark anything unverified as `Needs Verification`.
4. Add the old path to the migration table in `docs/INDEX.md`.
5. Do not delete the source doc until the new canonical doc is in place and linked.

## Changelog expectations

Every module `CHANGELOG.md` starts with a documentation baseline entry and should record:
- canonical doc creation
- major doc restructures
- scope changes
- retirement or legacy decisions

## Quality checks

Before finalizing a doc update:
- verify links resolve
- verify code paths exist
- verify route names and endpoints match source files
- verify permissions and error codes are copied from code or marked as unverified
- verify customer docs do not expose unnecessary backend internals
