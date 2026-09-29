from pathlib import Path
import runpy

from skullpix import load_asset, metadata_bytes, png_bytes, render_tileset, validate_asset


ROOT = Path(__file__).resolve().parents[1]


def test_stone_example_contracts_and_repeated_export():
    asset = load_asset(ROOT / "examples/stone_tiles.yaml")
    assert validate_asset(asset).valid
    first = render_tileset(asset, "stone")
    second = render_tileset(asset, "stone")
    assert first.image.size == (128, 96)
    assert len(first.metadata["tiles"]) == 10
    assert len(first.metadata["seams"]) == 19
    assert first.image.getpixel((127, 95)) == (0, 0, 0, 0)
    assert png_bytes(first.image) == png_bytes(second.image)
    assert metadata_bytes(first.metadata) == metadata_bytes(second.metadata)


def test_example_room_only_places_declared_tiles(tmp_path, monkeypatch):
    from PIL import Image

    monkeypatch.chdir(tmp_path)
    script = runpy.run_path(str(ROOT / "examples/stone_room.py"))
    names = set(load_asset(ROOT / "examples/stone_tiles.yaml").frames)
    assert all(name in names for row in script["ROOM"] for name in row if name)
    script["main"]()
    with Image.open(tmp_path / "build/tilesets/stone-room.png") as room:
        assert room.size == (384, 256)
        assert room.getpixel((40, 40)) == (0, 0, 0, 0)
