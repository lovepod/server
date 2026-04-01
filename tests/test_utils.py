from __future__ import annotations

import zlib

import pytest

from app.image_utils import compress_image, decompress_image
from app.secret_key_util import generate_box_secret_key
from app.utils.file_utils import sanitize_upload_filename


def test_compress_and_decompress_round_trip() -> None:
    payload = b"love" * 32
    compressed = compress_image(payload)

    assert compressed != payload
    assert decompress_image(compressed) == payload


def test_decompress_invalid_payload_raises() -> None:
    with pytest.raises(zlib.error):
        decompress_image(b"not-deflate")


def test_sanitize_upload_filename_uses_basename() -> None:
    assert sanitize_upload_filename("../nested/hello.png") == "hello.png"
    assert sanitize_upload_filename("  /tmp/file.gif  ") == "file.gif"
    assert sanitize_upload_filename(None) == "upload.bin"


def test_generate_box_secret_key_uses_requested_length_and_charset() -> None:
    secret = generate_box_secret_key(12)

    assert len(secret) == 12
    assert secret.isalnum()
    assert all(ch.isdigit() or ("A" <= ch <= "Z") for ch in secret)


def test_generate_box_secret_key_rejects_non_positive_length() -> None:
    with pytest.raises(ValueError, match="length must be positive"):
        generate_box_secret_key(0)
