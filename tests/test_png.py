from io import BytesIO
import struct
import zlib

from PIL import Image

from skullpix import png_bytes, render_asset, save_png


def test_canonical_png_roundtrip_and_only_required_chunks(make_asset):
    image = render_asset(make_asset([{"pixel": {"at": [2, 1], "color": "#ff000080"}}]))
    image.info.update({"date": "different each run", "icc_profile": b"unwanted"})
    data = png_bytes(image)
    assert data.startswith(b"\x89PNG\r\n\x1a\n")
    chunks = []
    offset = 8
    while offset < len(data):
        size = struct.unpack_from(">I", data, offset)[0]
        kind = data[offset + 4:offset + 8]
        body = data[offset + 8:offset + 8 + size]
        crc = struct.unpack_from(">I", data, offset + 8 + size)[0]
        assert crc == zlib.crc32(kind + body)
        chunks.append((kind, body))
        offset += 12 + size
    assert [kind for kind, _ in chunks] == [b"IHDR", b"IDAT", b"IEND"]
    rows = zlib.decompress(chunks[1][1])
    assert len(rows) == 5 * (1 + 5 * 4)
    assert all(rows[y * 21] == 0 for y in range(5))
    decoded = Image.open(BytesIO(data))
    assert decoded.mode == "RGBA"
    assert decoded.tobytes() == image.tobytes()


def test_png_multiple_deflate_blocks_and_repeatability(tmp_path):
    image = Image.new("RGBA", (200, 100), (12, 34, 56, 78))
    first, second = tmp_path / "a.png", tmp_path / "nested" / "b.png"
    save_png(image, first)
    save_png(image, second)
    assert first.read_bytes() == second.read_bytes() == png_bytes(image)
    assert Image.open(first).tobytes() == image.tobytes()


def test_pillow_api_save_is_repeatable_in_same_environment(make_asset):
    a, b = BytesIO(), BytesIO()
    image = render_asset(make_asset())
    image.save(a, format="PNG")
    image.save(b, format="PNG")
    assert a.getvalue() == b.getvalue()
