from __future__ import annotations

import logging
import os


def configure_logging() -> None:
    """
    Minimal, deterministic logging setup.

    - Avoids adding external logging frameworks.
    - Keeps logs readable in Docker and local dev.
    """

    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    if root.handlers:
        # Avoid double-configuring when reloading in dev.
        root.setLevel(level)
        return

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

