# Backend CI/CD

## Workflows
- `backend-ci.yml` - fast gate for lint, targeted typecheck, and fast pytest
- `backend-integration.yml` - migrations, API/integration/contract tests, DB smoke, OpenAPI snapshot check
- `backend-nightly.yml` - live golden API journeys against a compose-backed backend

## Backend CI/CD optimizations
- Fast gate installs only `backend/requirements-ci.txt` to avoid pulling the full ML/vision runtime.
- Integration and nightly workflows print `df -h` and `docker system df` before and after the compose-backed gates.
- Integration and nightly workflows upload compose logs only on failure with short retention.
- GitHub-hosted runners reclaim disk before compose jobs by removing unused Android, .NET, GHC, and CodeQL toolchains.

## Direct local commands
- Fast gate:
  - `cd backend && python3 -m pip install -r requirements-ci.txt && python3 -m ruff check app/core app/auth app/shared tests/support tests/domains/platform scripts && python3 -m mypy --follow-imports=skip app/core app/shared tests/support scripts/openapi_snapshot.py scripts/db_vnext_smoke_test.py app/api/v1/health.py && pytest -q -c tests/pytest.ini -m "not slow and not e2e and not golden" tests/domains/profile_change/unit`
- Integration gate:
  - `./scripts/backend-integration.sh`
- Golden journeys:
  - `RUN_GOLDEN=1 ./scripts/backend-nightly.sh`

## `act` commands
- Apple Silicon:
  - add `--container-architecture linux/amd64`
- Fast backend CI:
  - `act pull_request -W .github/workflows/backend-ci.yml --container-architecture linux/amd64`
- Integration:
  - `act pull_request -W .github/workflows/backend-integration.yml --container-architecture linux/amd64`
- Nightly/manual:
  - `act workflow_dispatch -W .github/workflows/backend-nightly.yml --container-architecture linux/amd64`

## Environment defaults
- Fast gate uses:
  - `DATABASE_URL=postgresql+psycopg://attendance:attendance@localhost:5432/attendance`
  - `REDIS_URL=redis://localhost:6379/0`
- Integration and nightly use `docker-compose.yaml` plus `backend/.env.docker`

## Troubleshooting
- `act` needs Docker Desktop running and a working Docker socket.
- Disk pressure is most likely in compose-backed jobs; inspect the `GITHUB_STEP_SUMMARY`, `df -h`, and `docker system df` output first.
- If compose jobs leave containers behind:
  - `docker compose down -v --remove-orphans`
- If nightly cannot reach the API service, inspect:
  - `docker compose --profile backend-ci logs backend_ci`
- If OpenAPI snapshot fails intentionally after contract changes:
  - regenerate it with `cd backend && python3 scripts/openapi_snapshot.py`
