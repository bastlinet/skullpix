"""Canonical RGBA8 PNG: filter 0, stored DEFLATE, no ancillary metadata.

Stored blocks deliberately trade compression for byte identity across zlib
versions. Pillow remains the raster engine and can decode these standard PNGs.
"""

import os
from pathlib import Path
import struct
import tempfile
import zlib

from PIL import Image


def _chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))


def png_bytes(image: Image.Image) -> bytes:
    image = image.convert("RGBA")
    width, height = image.size
    if width < 1 or height < 1:
        raise ValueError("PNG dimensions must be positive")
    pixels = image.tobytes()
    stride = width * 4
    raw = b"".join(b"\x00" + pixels[y * stride:(y + 1) * stride] for y in range(height))
    compressed = bytearray(b"\x78\x01")  # RFC 1950: deflate, 32 KiB window, no dictionary.
    for start in range(0, len(raw), 65535):
        block = raw[start:start + 65535]
        final = start + len(block) == len(raw)
        compressed.extend(struct.pack("<BHH", int(final), len(block), len(block) ^ 0xffff))
        compressed.extend(block)
    compressed.extend(struct.pack(">I", zlib.adler32(raw)))
    header = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", header)
            + _chunk(b"IDAT", bytes(compressed)) + _chunk(b"IEND", b""))


def save_png(image: Image.Image, path: str | Path) -> None:
    """Atomically write canonical PNG bytes, creating parent directories."""
    write_bytes_atomic(path, png_bytes(image))


def write_bytes_atomic(path: str | Path, data: bytes) -> None:
    """Shared atomic writer for PNG, metadata and preview files."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(data)
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
