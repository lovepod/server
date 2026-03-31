from __future__ import annotations

import secrets
import string

_ALPHABET = string.ascii_uppercase + string.digits


def generate_box_secret_key(length: int) -> str:
    """Alphanumeric secret (A–Z, 0–9), same style as legacy Java client."""
    if length < 1:
        raise ValueError("length must be positive")
    return "".join(secrets.choice(_ALPHABET) for _ in range(length))
