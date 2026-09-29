from io import BytesIO
import json

from PIL import Image
import pytest

from skullpix import Asset, AssetError, png_bytes, render_frame
from skullpix.animation import metadata_bytes, preview_bytes, render_sheet


def asset_for_animation(*, fps=8, loop=True, order=None):
    return Asset.model_validate({
        "canvas": {"width": 3, "height": 2, "background": "clear"},
        "palette": {"clear": "#00000000", "red": "#ff0000", "blue": "#0000ff"},
        "layers": [{"name": "body", "operations": [
            {"pixel": {"at": [0, 0], "color": "red"}}]}],
        "frames": {"a": {}, "b": {"extends": "a", "overrides": {"body": {
            "transform": {"translate": [1, 0]},
            "operations": [{"pixel": {"at": [0, 0], "color": "blue"}}]}}}},
        "animations": {"idle": {"fps": fps, "loop": loop, "frames": order or ["b", "a", "b"]}},
    })


def test_render_frame_reuses_single_canvas_renderer():
    asset = asset_for_animation()
    assert render_frame(asset, "a", strict=True).getpixel((0, 0)) == (255, 0, 0, 255)
    assert render_frame(asset, "b", strict=True).getpixel((1, 0)) == (0, 0, 255, 255)
    assert render_frame(asset, "b", strict=True).getpixel((0, 0))[3] == 0


def test_sheet_cells_have_explicit_order_coordinates_and_transparency():
    sheet = render_sheet(asset_for_animation(), "idle")
    assert sheet.image.mode == "RGBA"
    assert sheet.image.size == (9, 2)
    assert sheet.image.getpixel((1, 0)) == (0, 0, 255, 255)
    assert sheet.image.getpixel((3, 0)) == (255, 0, 0, 255)
    assert sheet.image.getpixel((7, 0)) == (0, 0, 255, 255)
    assert sheet.image.getpixel((0, 1)) == (0, 0, 0, 0)
    assert sheet.metadata == {
        "animation": "idle", "fps": 8, "loop": True,
        "frame_width": 3, "frame_height": 2,
        "frames": [
            {"name": "b", "x": 0, "y": 0, "w": 3, "h": 2, "duration_ms": 125},
            {"name": "a", "x": 3, "y": 0, "w": 3, "h": 2, "duration_ms": 125},
            {"name": "b", "x": 6, "y": 0, "w": 3, "h": 2, "duration_ms": 125},
        ],
    }


def test_metadata_rounding_loop_flag_and_trailing_newline():
    sheet = render_sheet(asset_for_animation(fps=7, loop=False), "idle")
    assert sheet.metadata["loop"] is False
    assert [row["duration_ms"] for row in sheet.metadata["frames"]] == [143, 143, 143]
    data = metadata_bytes(sheet.metadata)
    assert data.endswith(b"\n")
    assert json.loads(data)["fps"] == 7
    assert data == metadata_bytes(render_sheet(asset_for_animation(fps=7, loop=False), "idle").metadata)
    assert data.index(b'"animation"') < data.index(b'"fps"') < data.index(b'"frames"')


def test_repeated_sheets_are_byte_identical():
    asset = asset_for_animation()
    first = png_bytes(render_sheet(asset, "idle").image)
    second = png_bytes(render_sheet(asset, "idle").image)
    assert first == second


def test_gif_preview_has_explicit_frames_transparency_and_loop_timing():
    data = preview_bytes(asset_for_animation(), "idle")
    assert data == preview_bytes(asset_for_animation(), "idle")
    gif = Image.open(BytesIO(data))
    assert gif.format == "GIF"
    assert gif.n_frames == 3
    assert gif.info["loop"] == 0
    assert gif.info["duration"] == 130  # GIF uses 10 ms ticks; 125 rounds up.
    assert gif.convert("RGBA").getpixel((1, 0))[:3] == (0, 0, 255)
    gif.seek(1)
    assert gif.info["duration"] == 130
    assert gif.convert("RGBA").getpixel((0, 0))[:3] == (255, 0, 0)


def test_nonlooping_preview_omits_repeat_extension():
    gif = Image.open(BytesIO(preview_bytes(asset_for_animation(loop=False), "idle")))
    assert "loop" not in gif.info


@pytest.mark.parametrize("color", ["#3b0000", "#2c0000"])
@pytest.mark.parametrize("sequence", [["on", "off", "on"], ["on", "off"]])
def test_gif_preserves_fully_transparent_frames(color, sequence):
    asset = Asset.model_validate({
        "canvas": {"width": 2, "height": 1},
        "layers": [{"name": "p", "operations": [
            {"pixel": {"at": [0, 0], "color": color}}]}],
        "frames": {"on": {}, "off": {"overrides": {"p": {"visible": False}}}},
        "animations": {"flash": {"fps": 8, "frames": sequence}},
    })
    data = preview_bytes(asset, "flash")
    assert data.count(b"GIF89a") == 1
    with Image.open(BytesIO(data)) as gif:
        assert gif.n_frames == len(sequence)
        for index, name in enumerate(sequence):
            gif.seek(index)
            assert gif.info["duration"] == 130
            assert (gif.convert("RGBA").getpixel((0, 0))[3] > 0) == (name == "on")


def test_gif_preserves_long_repeated_poses_without_duration_overflow():
    asset = asset_for_animation(fps=1, order=["a"] * 700)
    with Image.open(BytesIO(preview_bytes(asset, "idle"))) as gif:
        assert gif.n_frames == 700
        for index in (0, 350, 699):
            gif.seek(index)
            assert gif.info["duration"] == 1000


def test_unknown_animation_has_structured_api_error():
    with pytest.raises(AssetError) as exc:
        render_sheet(asset_for_animation(), "missing")
    assert (exc.value.result.errors[0].code, exc.value.result.errors[0].path) == (
        "E057", "animations.missing")


def test_sheet_rejects_oversize_layout_before_allocation():
    asset = Asset.model_validate({
        "canvas": {"width": 4096, "height": 4096},
        "frames": {"a": {}},
        "animations": {"idle": {"fps": 8, "frames": ["a", "a"]}},
    })
    with pytest.raises(AssetError) as exc:
        render_sheet(asset, "idle")
    assert exc.value.result.errors[0].code == "E058"


def test_gif_uses_distinct_transparency_and_opaque_black_indexes():
    asset = Asset.model_validate({
        "canvas": {"width": 2, "height": 1},
        "layers": [{"name": "body", "operations": [
            {"pixel": {"at": [0, 0], "color": "#000000ff"}},
            {"pixel": {"at": [1, 0], "color": "#ff000040"}},
        ]}],
        "frames": {"a": {}},
        "animations": {"idle": {"fps": 5, "frames": ["a"]}},
    })
    gif = Image.open(BytesIO(preview_bytes(asset, "idle")))
    assert gif.convert("RGBA").getpixel((0, 0)) == (0, 0, 0, 255)
    assert gif.convert("RGBA").getpixel((1, 0))[3] == 0
