from hashlib import sha256
import json
from pathlib import Path

import pytest

from skullpix import lint_asset, load_asset, png_bytes, render_frame, validate_asset
from skullpix.animation import metadata_bytes, preview_bytes, render_sheet

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples" / "animated_skeleton.yaml"


@pytest.mark.parametrize("name,count", [("idle", 6), ("walk", 8), ("attack", 4)])
def test_animated_skeleton_is_compact_valid_and_golden(name, count):
    asset = load_asset(SOURCE)
    assert validate_asset(asset).valid
    assert lint_asset(asset).valid
    assert len(asset.animations[name].frames) == count
    assert len(asset.frames) == 18
    assert all(len(frame.overrides) <= 3 for frame in asset.frames.values())
    sheet = render_sheet(asset, name)
    assert sheet.image.size == (32 * count, 32)
    assert [record["name"] for record in sheet.metadata["frames"]] == asset.animations[name].frames
    hashes = json.loads((ROOT / "tests" / "golden_sha256.json").read_text())
    assert sha256(png_bytes(sheet.image)).hexdigest() == hashes[f"animated_skeleton-{name}.png"]
    assert sha256(metadata_bytes(sheet.metadata)).hexdigest() == hashes[f"animated_skeleton-{name}.json"]


def test_skeleton_animation_phases_are_visibly_distinct():
    asset = load_asset(SOURCE)
    for left, right in (("idle_0", "idle_1"), ("walk_0", "walk_4"), ("attack_0", "attack_2")):
        assert render_frame(asset, left, strict=True).tobytes() != render_frame(asset, right, strict=True).tobytes()
    gif = preview_bytes(asset, "idle")
    assert gif == preview_bytes(asset, "idle")
