from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _normalize_openapi(doc: dict) -> dict:
    normalized = dict(doc)
    normalized.pop("servers", None)
    return normalized


def _snapshot_path() -> Path:
    configured = os.getenv("OPENAPI_SNAPSHOT_PATH")
    if configured:
        return Path(configured)

    backend_dir = _backend_dir()
    repo_docs = backend_dir.parent / "docs" / "openapi" / "backend.openapi.snapshot.json"
    if repo_docs.parent.exists():
        return repo_docs

    mounted_docs = Path("/docs/openapi/backend.openapi.snapshot.json")
    if mounted_docs.parent.exists():
        return mounted_docs

    return repo_docs


def _render_snapshot() -> str:
    backend_dir = _backend_dir()
    if str(backend_dir) not in sys.path:
        sys.path.insert(0, str(backend_dir))

    from app.main import create_app

    doc = _normalize_openapi(create_app().openapi())
    return json.dumps(doc, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Fail if the generated snapshot differs.")
    args = parser.parse_args()

    snapshot_path = _snapshot_path()
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    rendered = _render_snapshot()
    if args.check:
        if not snapshot_path.exists():
            print(f"Missing OpenAPI snapshot: {snapshot_path}", file=sys.stderr)
            return 1
        current = snapshot_path.read_text(encoding="utf-8")
        if current != rendered:
            print(f"OpenAPI snapshot drift detected: {snapshot_path}", file=sys.stderr)
            return 1
        return 0

    snapshot_path.write_text(rendered, encoding="utf-8")
    print(snapshot_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
