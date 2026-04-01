"""Kompresija/dekompresija kao Java Deflater/Inflater (raw deflate, bez zlib wrappera).

Plus: server-side image optimization for embedded clients (resize to fit display, cap bytes).
"""

from __future__ import annotations

import zlib
from io import BytesIO


def compress_image(data: bytes) -> bytes:
    c = zlib.compressobj(level=zlib.Z_BEST_COMPRESSION, wbits=-zlib.MAX_WBITS)
    out = c.compress(data) + c.flush()
    return out


def decompress_image(data: bytes) -> bytes:
    return zlib.decompress(data, wbits=-zlib.MAX_WBITS)


def optimize_for_embedded_display(
    raw: bytes,
    content_type: str,
    *,
    max_w: int = 320,
    max_h: int = 240,
    target_max_bytes: int = 60_000,
) -> tuple[bytes, str]:
    """
    Resize images to fit the target display and keep payload small enough that embedded clients
    can read via JSON/base64 without OOM.

    Returns (optimized_bytes, optimized_content_type).
    - For PNG/JPEG: performs EXIF-aware transpose, thumbnail to max_w/max_h.
    - Uses JPEG output (smaller) when needed; PNG output preserved only if small enough.
    """
    ct = (content_type or "").strip().lower()
    if not ct.startswith("image/"):
        return raw, content_type
    if ct == "image/gif":
        # Keep GIF as-is (resizing animated GIF safely is more complex).
        return raw, content_type

    try:
        from PIL import Image, ImageOps  # type: ignore
    except Exception:
        # Pillow not available in runtime (or failed to load native codecs) — keep as-is.
        return raw, content_type

    try:
        img = Image.open(BytesIO(raw))
        img = ImageOps.exif_transpose(img)
    except Exception:
        # Not a decodable raster image (or corrupt) — keep as-is.
        return raw, content_type

    # Convert to a safe mode for resizing/encoding.
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")

    img.thumbnail((max_w, max_h), Image.Resampling.LANCZOS)

    # First try: keep PNG if it is already PNG and small enough after resize.
    if ct in ("image/png", "image/x-png"):
        buf = BytesIO()
        try:
            img.save(buf, format="PNG", optimize=True, compress_level=9)
            out = buf.getvalue()
            if len(out) <= target_max_bytes:
                return out, "image/png"
        except Exception:
            pass

    # Default: encode JPEG (drops alpha on black background).
    if img.mode == "RGBA":
        bg = Image.new("RGB", img.size, (0, 0, 0))
        bg.paste(img, mask=img.getchannel("A"))
        img_rgb = bg
    else:
        img_rgb = img.convert("RGB")

    # Try a few quality levels to hit target_max_bytes.
    for q in (80, 70, 60, 50, 40, 30):
        buf = BytesIO()
        img_rgb.save(buf, format="JPEG", quality=q, optimize=True, progressive=False)
        out = buf.getvalue()
        if len(out) <= target_max_bytes:
            return out, "image/jpeg"

    # Last resort: return smallest we got.
    buf = BytesIO()
    img_rgb.save(buf, format="JPEG", quality=25, optimize=True, progressive=False)
    return buf.getvalue(), "image/jpeg"
