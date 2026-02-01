"""
Compatibility wrapper.

The canonical DB vNext smoke test lives at:
  backend/tests/db_vnext_smoke_test.py

This wrapper keeps older docs/compose commands working.
"""

from __future__ import annotations

import runpy
from pathlib import Path


def main() -> int:
    backend_dir = Path(__file__).resolve().parents[1]
    script = backend_dir / "tests" / "db_vnext_smoke_test.py"
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

