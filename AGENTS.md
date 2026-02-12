# Repository Guidelines

## Project Structure & Module Organization
- `backend/`: FastAPI service, RQ workers, SQLAlchemy models, and Alembic migrations.
- `backend/app/`: API routes, domain logic, background tasks.
- `backend/alembic/`: Database migrations.
- `backend/tests/`: Pytest suite and smoke tests.
- `frontend/`: Next.js web app (admin/import UI and general web).
- `mobile-application/`: Expo React Native client.
- `docs/`: Design and DB reference docs.
- `docker-compose.yaml`: Local multi-service dev (API, web, Postgres, Redis, workers).
- Persistent dev data/artifacts live under `backend/data/` and models under `backend/models/` (mounted in Docker).

## Build, Test, and Development Commands
- `docker compose up --build`: Run full stack locally (web, API, DB, workers).
- `python3 backend/scripts/run_all_tests.py`: Run backend smoke test + pytest suite.
- `cd backend && pytest -q`: Run backend tests only.
- `cd frontend && npm run dev`: Start Next.js dev server.
- `cd frontend && npm run build`: Production build.
- `cd frontend && npm run lint`: Run ESLint.
- `cd mobile-application && npm start`: Start Expo dev server.
- `cd mobile-application && npm run android|ios|web`: Platform-specific builds.

## Coding Style & Naming Conventions
- Python: follow existing FastAPI/SQLAlchemy patterns in `backend/app/`; use type hints where already present.
- JavaScript/TypeScript: follow Next.js conventions in `frontend/`; keep components and hooks named in `PascalCase`/`camelCase`.
- Formatting/linting: ESLint configured in `frontend/eslint.config.mjs`; use `npm run lint` before PRs.
- Prefer descriptive module names aligned to domain areas (e.g., `hr`, `iam`, `tenancy`).

## Testing Guidelines
- Backend uses Pytest (`backend/tests/`).
- Some tests require a fresh DB; read skip messages in failing tests for reset guidance.
- Use `backend/scripts/run_all_tests.py` to include DB vNext smoke checks.

## Commit & Pull Request Guidelines
- Recent commits use short, sentence-style messages (sometimes multi-clause, occasional emoji). Keep messages concise and imperative (e.g., "Add HR screening run API").
- PRs should include: a clear summary, steps to test, and screenshots for UI changes.
- Link relevant issues or docs (e.g., `docs/DB_VNEXT.md`) when modifying schemas.

## Security & Configuration Tips
- Sensitive config is env-driven (e.g., `GEMINI_API_KEY`, `FIREBASE_SERVICE_ACCOUNT_PATH`). Do not commit secrets.
- For local admin access, `ADMIN_PASSWORD` defaults to `admin` in Docker Compose; override for shared environments.
