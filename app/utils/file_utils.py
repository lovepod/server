"""Safe filename handling for uploads."""

from __future__ import annotations

import os


def sanitize_upload_filename(name: str | None, fallback: str = "upload.bin") -> str:
    if not name:
        return fallback
    base = os.path.basename(name.strip())
    return base if base else fallback
