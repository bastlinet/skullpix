from copy import deepcopy

import pytest

from skullpix import (
    Asset, AssetError, inspect_asset, lint_asset, metadata_bytes, png_bytes,
    preview_bytes, render_asset, render_frame, render_sheet, resolve_frame,
    validate_asset,
)
from skullpix.tilesets import render_tileset


def grid_asset():
    return Asset.model_validate({
        "canvas": {"width": 3, "height": 2, "background": "#010203"},
        "layers": [{"name": "paint"}],
        "frames": {name: {"overrides": {"paint": {"operations": [
            {"rect": {"box": [0, 0, 3, 2], "color": color}}]}}}
            for name, color in [("a", "#ff0000"), ("b", "#00ff00"), ("c", "#0000ff")]},
        "tilesets": {"grid": {"columns": 2, "tiles": ["b", "a", "c"]}},
    })


def edge_asset(first, second, axis="x"):
    height, width = len(first), len(first[0])
    frames = {}
    for name, rows in (("a", first), ("b", second)):
        frames[name] = {"overrides": {"pixels": {"operations": [
            {"pixel": {"at": [x, y], "color": color}}
            for y, row in enumerate(rows) for x, color in enumerate(row)
        ]}}}
    return Asset.model_validate({
        "canvas": {"width": width, "height": height}, "layers": [{"name": "pixels"}],
        "frames": frames, "animations": {"idle": {"fps": 10, "frames": ["a", "b"]}},
        "tilesets": {"grid": {"columns": 2, "tiles": ["a", "b"],
            "seams": [{"from": "a", "to": "b", "axis": axis}]}},
    })


R, G, B, CLEAR = "#ff0000", "#00ff00", "#0000ff", "#00000000"


def test_grid_exact_pixels_ids_and_transparent_unused_cell():
    result = render_tileset(grid_asset(), "grid")
    assert result.image.size == (6, 4)
    expected = [[(0, 255, 0, 255)] * 3 + [(255, 0, 0, 255)] * 3] * 2
    expected += [[(0, 0, 255, 255)] * 3 + [(0, 0, 0, 0)] * 3] * 2
    assert list(result.image.get_flattened_data()) == [pixel for row in expected for pixel in row]
    assert result.metadata == {
        "tileset": "grid", "tile_width": 3, "tile_height": 2, "columns": 2, "rows": 2,
        "tiles": [
            {"id": 0, "name": "b", "x": 0, "y": 0, "w": 3, "h": 2},
            {"id": 1, "name": "a", "x": 3, "y": 0, "w": 3, "h": 2},
            {"id": 2, "name": "c", "x": 0, "y": 2, "w": 3, "h": 2},
        ], "seams": [],
    }


def test_grid_repeated_bytes_and_metadata_key_order():
    asset = grid_asset()
    before = deepcopy(asset.model_dump())
    first, second = render_tileset(asset, "grid"), render_tileset(asset, "grid")
    assert png_bytes(first.image) == png_bytes(second.image)
    assert metadata_bytes(first.metadata) == metadata_bytes(second.metadata)
    assert metadata_bytes(first.metadata).startswith(b'{\n  "tileset": "grid",\n  "tile_width": 3,\n')
    assert metadata_bytes(first.metadata).endswith(b"\n")
    assert asset.model_dump() == before
    first.image.putpixel((0, 0), (0, 0, 0, 0))
    first.metadata["tiles"][0]["name"] = "changed"
    assert render_tileset(asset, "grid").metadata["tiles"][0]["name"] == "b"
    assert render_tileset(asset, "grid").image.getpixel((0, 0)) == (0, 255, 0, 255)


def test_inherited_operations_and_translation_reuse_existing_renderer():
    asset = Asset.model_validate({"canvas": {"width": 3, "height": 2},
        "layers": [{"name": "p", "operations": [{"pixel": {"at": [0, 0], "color": R}}]}],
        "frames": {"root": {}, "child": {"extends": "root", "overrides": {
            "p": {"transform": {"translate": [1, 1]}}}}},
        "tilesets": {"grid": {"columns": 1, "tiles": ["child", "root"]}}})
    result = render_tileset(asset, "grid")
    occupied = [(x, y) for y in range(4) for x in range(3) if result.image.getpixel((x, y))[3]]
    assert occupied == [(1, 1), (0, 2)]
    assert resolve_frame(asset, "child").tilesets == {}


@pytest.mark.parametrize("axis,a,b", [
    ("x", [[B, R], [R, G]], [[R, G], [G, B]]),
    ("y", [[B, B, B], [R, G, B]], [[R, G, B], [G, R, R]]),
])
def test_exact_seams_in_both_directions(axis, a, b):
    asset = edge_asset(a, b, axis)
    assert validate_asset(asset).valid
    assert lint_asset(asset).valid
    assert render_tileset(asset, "grid").metadata["seams"] == [
        {"from": "a", "to": "b", "axis": axis}]


def test_self_seams_and_no_implicit_checks():
    asset = edge_asset([[R, G, R]], [[B, G, R]])
    data = asset.model_dump(by_alias=True)
    data["tilesets"]["grid"]["seams"] = [{"from": "a", "to": "a", "axis": "x"}]
    assert validate_asset(Asset.model_validate(data)).valid
    data["tilesets"]["grid"]["seams"] = []
    assert validate_asset(Asset.model_validate(data)).valid


def test_mismatched_edge_reports_exact_location_values_and_count():
    asset = edge_asset([[B, R], [B, G]], [[G, B], [R, B]])
    for strict in (True, False):
        result = validate_asset(asset, strict=strict)
        issue = next(i for i in result.errors if i.code == "E076")
        assert issue.path == "tilesets.grid.seams[0]"
        assert issue.value == {"from": "a", "to": "b", "axis": "x", "mismatched_pixels": 2,
            "edge_pixels": 2, "first_mismatch": {"offset": 0, "from": [255, 0, 0, 255],
                                               "to": [0, 255, 0, 255]}}


def test_alpha_is_compared_but_hidden_rgb_is_normalized():
    assert validate_asset(edge_asset([["#ff000000"]], [["#abcdef00"]])).valid
    issue = validate_asset(edge_asset([["#ff000080"]], [[R]])).errors[0]
    assert issue.code == "E076"
    assert issue.value["first_mismatch"]["from"] == [255, 0, 0, 128]


@pytest.mark.parametrize("entry", [
    lambda a: render_tileset(a, "grid"), render_asset, inspect_asset,
    lambda a: render_frame(a, "a"), lambda a: render_sheet(a, "idle"),
    lambda a: preview_bytes(a, "idle"),
])
def test_all_export_entry_points_reject_invalid_declared_seams(entry):
    with pytest.raises(AssetError) as exc:
        entry(edge_asset([[R]], [[B]]))
    assert any(i.code == "E076" for i in exc.value.result.errors)


def test_bad_frame_does_not_crash_seam_analysis():
    data = edge_asset([[R]], [[R]]).model_dump(by_alias=True)
    data["frames"]["b"]["extends"] = "absent"
    assert validate_asset(Asset.model_validate(data)).errors[0].code == "E050"
    data["frames"]["b"].pop("extends")
    data["frames"]["b"]["overrides"]["pixels"]["operations"][0]["pixel"]["color"] = "absent"
    assert any(i.code == "E012" for i in validate_asset(Asset.model_validate(data)).errors)


def test_unknown_selector_is_structured_with_suggestion():
    with pytest.raises(AssetError) as exc:
        render_tileset(grid_asset(), "gird")
    issue = exc.value.result.errors[0]
    assert (issue.code, issue.path, issue.suggestions) == ("E070", "tilesets.gird", ("grid",))


@pytest.mark.parametrize("width,height,columns,count", [
    (4096, 1, 16, 1), (1, 4096, 1, 16), (4096, 4096, 2, 1),
])
def test_grid_limits_are_checked_before_any_render(monkeypatch, width, height, columns, count):
    import skullpix.tilesets as module

    def no_render(*args, **kwargs):
        pytest.fail("Oversized atlas reached validation/rendering")

    monkeypatch.setattr(module, "_validate_export", no_render)
    asset = Asset.model_validate({"canvas": {"width": width, "height": height},
        "frames": {f"f{i}": {} for i in range(count)},
        "tilesets": {"grid": {"columns": columns, "tiles": [f"f{i}" for i in range(count)]}}})
    with pytest.raises(AssetError) as exc:
        render_tileset(asset, "grid")
    assert exc.value.result.errors[0].code == "E077"


def test_columns_can_include_explicit_blank_cells():
    asset = Asset.model_validate({"canvas": {"width": 1, "height": 1, "background": R},
        "frames": {"a": {}}, "tilesets": {"grid": {"columns": 3, "tiles": ["a"]}}})
    assert list(render_tileset(asset, "grid").image.get_flattened_data()) == [
        (255, 0, 0, 255), (0, 0, 0, 0), (0, 0, 0, 0)]
