"""Configure stdlib logging for structured console output."""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str) -> None:
    root = logging.getLogger()
    root.setLevel(level)

    if not root.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%dT%H:%M:%S%z",
            )
        )
        root.addHandler(handler)

    # Reduce noise from libraries in production
    logging.getLogger("uvicorn.access").setLevel(logging.INFO)
