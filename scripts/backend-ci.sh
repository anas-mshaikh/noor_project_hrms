#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

export DATABASE_URL="${DATABASE_URL:-postgresql+psycopg://attendance:attendance@localhost:5432/attendance}"
export REDIS_URL="${REDIS_URL:-redis://localhost:6379/0}"
export PIP_DISABLE_PIP_VERSION_CHECK="${PIP_DISABLE_PIP_VERSION_CHECK:-1}"

cd "$BACKEND_DIR"
df -h
python3 -m pip install --no-input -r requirements-ci.txt
python3 -m ruff check app/core app/auth app/shared tests/support tests/domains/platform scripts
python3 -m mypy --follow-imports=skip app/core app/shared tests/support scripts/openapi_snapshot.py scripts/db_vnext_smoke_test.py app/api/v1/health.py
pytest -q -c tests/pytest.ini -m "not slow and not e2e and not golden" tests/domains/profile_change/unit
df -h
