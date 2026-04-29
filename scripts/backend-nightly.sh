#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_GOLDEN="${RUN_GOLDEN:-1}"
status=0

cleanup() {
  if [[ "$status" -ne 0 ]]; then
    docker compose --profile backend-ci logs --no-color || true
  fi
  docker compose --profile backend-ci down -v --remove-orphans >/dev/null 2>&1 || true
  docker compose down -v --remove-orphans >/dev/null 2>&1 || true
}

trap 'status=$?; cleanup' EXIT

cd "$ROOT_DIR"
df -h
docker system df || true
docker compose --profile backend-ci up -d db redis
docker compose --profile backend-ci up --build --abort-on-container-exit backend_image migrate
docker compose --profile backend-ci up -d backend_ci

if [[ "$RUN_GOLDEN" == "1" ]]; then
  SKIP_TESTS=0 docker compose --profile backend-ci run --rm -e BASE_URL=http://backend_ci:8000 backend_tests pytest -q -c tests/pytest.ini -m golden
fi

df -h
docker system df || true
