import json

import pytest

from skullpix import Asset, AssetError, load_asset, resolve_frame, validate_asset


def source(**tileset):
    return {"canvas": {"width": 3, "height": 2}, "frames": {"plain": {}, "cracked": {}},
            "tilesets": {"stone": {"columns": 2, "tiles": ["plain", "cracked"], **tileset}}}


def test_named_tileset_preserves_order_and_frame_resolution_is_standalone():
    asset = Asset.model_validate(source(tiles=["cracked", "plain"]))
    assert asset.tilesets["stone"].tiles == ["cracked", "plain"]
    assert validate_asset(asset).valid
    frame = resolve_frame(asset, "plain")
    assert frame.tilesets == {}
    assert validate_asset(frame).valid


@pytest.mark.parametrize("columns", [0, -1, 1.5, "2", True, 4097, None])
def test_columns_are_strict_positive_integers(tmp_path, columns):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(source(columns=columns)))
    with pytest.raises(AssetError) as exc:
        load_asset(path)
    issue = exc.value.result.errors[0]
    assert (issue.code, issue.path) == ("E074", "tilesets.stone.columns")


def test_empty_tileset_and_missing_tiles_have_specific_diagnostic(tmp_path):
    for tiles in ([], None):
        data = source(tiles=[])
        if tiles is None:
            del data["tilesets"]["stone"]["tiles"]
        path = tmp_path / "bad.json"
        path.write_text(json.dumps(data))
        with pytest.raises(AssetError) as exc:
            load_asset(path)
        assert exc.value.result.errors[0].code == "E071"


@pytest.mark.parametrize("tiles", [None, "plain", {}, True, 3])
def test_wrong_type_tile_list_remains_schema_error(tmp_path, tiles):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(source(tiles=tiles)))
    with pytest.raises(AssetError) as exc:
        load_asset(path)
    assert exc.value.result.errors[0].code == "E002"


@pytest.mark.parametrize("change,code,path", [
    ({"tiles": ["plain", "plian"]}, "E072", "tilesets.stone.tiles[1]"),
    ({"tiles": ["plain", "plain"]}, "E073", "tilesets.stone.tiles[1]"),
    ({"seams": [{"from": "absent", "to": "plain", "axis": "x"}]}, "E075", "tilesets.stone.seams[0].from"),
    ({"tiles": ["plain"], "seams": [{"from": "plain", "to": "cracked", "axis": "y"}]},
     "E075", "tilesets.stone.seams[0].to"),
])
def test_reference_errors_have_source_paths(change, code, path):
    result = validate_asset(Asset.model_validate(source(**change)))
    assert not result.valid
    issue = next(i for i in result.errors if i.code == code)
    assert issue.path == path
    if code == "E072":
        assert issue.suggestions == ("plain",)


def test_invalid_tileset_without_frames_is_not_skipped():
    data = source()
    data["frames"] = {}
    result = validate_asset(Asset.model_validate(data))
    assert [issue.code for issue in result.errors] == ["E072", "E072"]


@pytest.mark.parametrize("axis", ["z", "X", 1, True, None])
def test_invalid_seam_axis_is_structured(tmp_path, axis):
    data = source(seams=[{"from": "plain", "to": "plain", "axis": axis}])
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(data))
    with pytest.raises(AssetError) as exc:
        load_asset(path)
    issue = exc.value.result.errors[0]
    assert (issue.code, issue.path) == ("E078", "tilesets.stone.seams[0].axis")
