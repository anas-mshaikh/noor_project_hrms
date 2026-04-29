# CI/CD

## Required checks
- PR CI: lint, typecheck, Vitest, and Next build.
- Integration CI: repo-root Docker Compose test gate.
- E2E Smoke: Playwright smoke via Docker Compose.
- Release Bundle: manual workflow to rerun gates, build frontend, and package release artifacts.

## GitHub workflows
- `.github/workflows/ci.yml`
- `.github/workflows/integration.yml`
- `.github/workflows/e2e.yml`
- `.github/workflows/release.yml`

## Run the same checks locally
### Frontend fast gate
```bash
cd frontend
npm ci
npm run lint
npx tsc --noEmit --pretty false
npm run test:ci
npm run build
```

### Integration gate
```bash
SKIP_TESTS=0 docker compose up --build --abort-on-container-exit --exit-code-from tests tests
```

### E2E smoke gate
```bash
docker compose --profile e2e up --build --abort-on-container-exit --exit-code-from frontend_e2e frontend_e2e
```

### Release-candidate drill
```bash
./scripts/rc-check.sh
RUN_E2E=1 ./scripts/rc-check.sh
```

## Run workflows locally with `act`
### PR CI
```bash
act push --container-architecture linux/amd64 -W .github/workflows/ci.yml
```

### Integration CI
```bash
act push --container-architecture linux/amd64 -W .github/workflows/integration.yml
```

### E2E smoke
```bash
act workflow_dispatch --container-architecture linux/amd64 -W .github/workflows/e2e.yml
```

### Release bundle
```bash
act workflow_dispatch --container-architecture linux/amd64 -W .github/workflows/release.yml -e <(printf '{"inputs":{"version":"v0.11.0-rc1"}}')
```

## `act` notes
- `act` uses Docker. Start Docker Desktop before running any workflow locally.
- On Apple Silicon, add `--container-architecture linux/amd64` if a runner image or container build fails on arm64.
- `act push` is the closest workflow-level simulation of the required PR and main-branch gates.
- Integration and e2e workflows call `docker compose` from inside the workflow. If your local `act` image does not expose the host Docker socket correctly, run the equivalent commands directly from the repo root instead.
- These workflows do not require application secrets for lint, typecheck, unit/component, integration, or smoke runs.
- Local `docker compose up` skips the compose test gate by default.
- Use `SKIP_TESTS=0` only when you intentionally want the compose-backed tests to run.
- CI must never use `SKIP_TESTS=1`. That escape hatch is for local dev containers only.
- `./scripts/rc-check.sh` is the canonical local release-candidate drill. Use `RUN_E2E=1 ./scripts/rc-check.sh` when you want the compose-backed smoke gate included.

## Troubleshooting
- Missing optional native Node package (`@rollup/rollup-darwin-arm64`, `lightningcss.darwin-arm64.node`): run `npm ci` again in `frontend/`.
- Docker Compose gate hangs: inspect `docker compose logs --no-color` and verify the `tests` service is waiting on `backend_tests` and `frontend_tests`.
- Playwright report is empty in CI: confirm `frontend/playwright-report/` and `frontend/test-results/` exist after the run.
- Scope-related test failures: clear browser storage/cookies or use the `Reset selection` action in the UI before rerunning the flow.
