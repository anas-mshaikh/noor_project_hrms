#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
status=0

cleanup() {
  if [[ "$status" -ne 0 ]]; then
    docker compose logs --no-color || true
  fi
  docker compose down -v --remove-orphans >/dev/null 2>&1 || true
}

trap 'status=$?; cleanup' EXIT

cd "$ROOT_DIR"
df -h
docker system df || true
docker compose up -d db redis
docker compose up --build --abort-on-container-exit backend_image migrate
SKIP_TESTS=0 docker compose run --rm backend_tests pytest -q -c tests/pytest.ini -m "api or integration or contract"
SKIP_TESTS=0 docker compose run --rm backend_tests python tests/smoke/test_db_vnext_smoke.py
SKIP_TESTS=0 docker compose run --rm backend_tests python scripts/openapi_snapshot.py --check
df -h
docker system df || true
