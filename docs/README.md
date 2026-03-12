# Documentation System

This directory is the canonical documentation system for Noor HRMS.

The documentation model is module-first:
- each business module owns one internal master document and one customer guide
- shared platform rules live under `docs/Shared/`
- module-specific deep dives live under `docs/Modules/<ModuleName>/Features/`
- legacy or transitional surfaces are documented explicitly rather than mixed into active HRMS modules

Start here:
- `docs/INDEX.md`
- `docs/MODULE_CATALOG.md`
- `docs/CONTRIBUTING.md`

Reference implementations:
- `docs/Modules/Leave/Leave.Internal.md`
- `docs/Modules/Leave/Leave.Customer.md`
- `docs/Modules/Leave/Features/`

Source-of-truth rule:
- superseded milestone and feature notes have been retired from the active docs tree
- module and shared docs are the authoritative references for engineering, product, design, QA, onboarding, and customer handoff

Support material kept outside the canonical tree:
- `docs/CI_CD/` for operational runbooks and release procedures
- `docs/backend/openapi/` for the backend API snapshot
- `docs/references/` for external reference PDFs
- `docs/Demo_videos/` for demo recordings
