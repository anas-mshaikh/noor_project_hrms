"""
run_all_tests.py

Single entrypoint to run all backend tests (current and future).

Usage:
  python scripts/run_all_tests.py

This runs:
1) DB vNext smoke test (if present): ./tests/smoke/test_db_vnext_smoke.py
2) pytest discovery on ./tests (domain-driven folders)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    # Ensure `import app` works when this file is executed as:
    #   /app/scripts/run_all_tests.py
    # because sys.path[0] would otherwise be /app/scripts.
    backend_dir = Path(__file__).resolve().parents[1]
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    tests_dir = backend_dir / "tests"

    # Run DB vNext smoke test first (fast schema sanity check).
    smoke = tests_dir / "smoke" / "test_db_vnext_smoke.py"
    if smoke.exists():
        proc = subprocess.run([sys.executable, str(smoke)], check=False)
        if proc.returncode != 0:
            return int(proc.returncode)

    try:
        import pytest
    except Exception as e:  # noqa: BLE001 - keep CLI user-friendly
        print(f"pytest import failed: {e}", file=sys.stderr)
        return 2

    # Keep CI-friendly defaults:
    # - Use tests/pytest.ini for marker definitions and shared options.
    # - Skip "slow" and live golden/e2e tests unless explicitly requested.
    #
    # Developers can override the marker expression by passing:
    #   PYTEST_MARK_EXPR="slow" python scripts/run_all_tests.py
    pytest_ini = tests_dir / "pytest.ini"
    marker_expr = "not slow and not e2e and not golden"
    if "PYTEST_MARK_EXPR" in os.environ:
        marker_expr = os.environ["PYTEST_MARK_EXPR"].strip() or marker_expr

    args = ["-q"]
    if pytest_ini.exists():
        args.extend(["-c", str(pytest_ini)])
    args.extend(["-m", marker_expr, str(tests_dir)])
    return int(pytest.main(args))


if __name__ == "__main__":
    raise SystemExit(main())
