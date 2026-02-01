"""
run_all_tests.py

Single entrypoint to run all backend tests (current and future).

Usage:
  python scripts/run_all_tests.py

This runs:
1) DB vNext smoke test (if present): ./tests/db_vnext_smoke_test.py
2) pytest discovery on ./tests
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    # Ensure `import app` works when this file is executed as /app/scripts/run_all_tests.py
    # (sys.path[0] would otherwise be /app/scripts).
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    tests_dir = Path(__file__).resolve().parents[1] / "tests"

    # Run DB vNext smoke test first (fast schema sanity check).
    smoke = tests_dir / "db_vnext_smoke_test.py"
    if smoke.exists():
        proc = subprocess.run([sys.executable, str(smoke)], check=False)
        if proc.returncode != 0:
            return int(proc.returncode)

    try:
        import pytest
    except Exception as e:  # noqa: BLE001 - keep CLI user-friendly
        print(f"pytest import failed: {e}", file=sys.stderr)
        return 2

    return int(pytest.main(["-q", "tests"]))


if __name__ == "__main__":
    raise SystemExit(main())
