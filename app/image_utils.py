"""Kompresija/dekompresija kao Java Deflater/Inflater (raw deflate, bez zlib wrappera)."""

from __future__ import annotations

import zlib


def compress_image(data: bytes) -> bytes:
    c = zlib.compressobj(level=zlib.Z_BEST_COMPRESSION, wbits=-zlib.MAX_WBITS)
    out = c.compress(data) + c.flush()
    return out


def decompress_image(data: bytes) -> bytes:
    return zlib.decompress(data, wbits=-zlib.MAX_WBITS)
