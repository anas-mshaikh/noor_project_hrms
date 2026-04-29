#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_E2E="${RUN_E2E:-0}"

cleanup() {
  docker compose down -v --remove-orphans >/dev/null 2>&1 || true
  docker compose --profile e2e down -v --remove-orphans >/dev/null 2>&1 || true
}

trap cleanup EXIT

cd "$ROOT_DIR/frontend"
npm ci
npm run lint
npx tsc --noEmit --pretty false
npm run test:ci
npm run build

cd "$ROOT_DIR"
SKIP_TESTS=0 docker compose up --build --abort-on-container-exit --exit-code-from tests tests

if [[ "$RUN_E2E" == "1" ]]; then
  docker compose --profile e2e up --build --abort-on-container-exit --exit-code-from frontend_e2e frontend_e2e
fi
