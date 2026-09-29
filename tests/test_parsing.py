import json

import pytest

from skullpix import Asset, AssetError, load_asset
from skullpix.palette import resolve_color


def test_yaml_and_json_load_same_asset(tmp_path):
    data = {"canvas": {"width": 3, "height": 2}, "palette": {"ink": "#123456"},
            "layers": [{"name": "a", "operations": [{"pixel": {"at": [1, 0], "color": "ink"}}]}]}
    path = tmp_path / "sprite.json"
    path.write_text(json.dumps(data))
    yaml = tmp_path / "sprite.yaml"
    yaml.write_text('canvas: {width: 3, height: 2}\npalette: {ink: "#123456"}\n'
                    'layers:\n- name: a\n  operations:\n  - pixel: {at: [1, 0], color: ink}\n')
    assert load_asset(path) == load_asset(yaml)
    assert load_asset(path).version == 1


@pytest.mark.parametrize("value", [True, 1.5, "2", 0, -1, 4097])
def test_dimensions_reject_coercion_and_invalid_sizes(value):
    with pytest.raises(ValueError):
        Asset.model_validate({"canvas": {"width": value, "height": 2}})


@pytest.mark.parametrize("value", [True, 1.0, "1", 2])
def test_version_is_strict(value):
    with pytest.raises(ValueError):
        Asset.model_validate({"version": value, "canvas": {"width": 2, "height": 2}})


@pytest.mark.parametrize("value", [True, 0.5, "1"])
def test_coordinate_is_strict(value):
    with pytest.raises(ValueError):
        Asset.model_validate({"canvas": {"width": 2, "height": 2}, "layers": [
            {"name": "a", "operations": [{"pixel": {"at": [value, 0], "color": "#123456"}}]}]})


@pytest.mark.parametrize("source,suffix,code", [
    ('canvas: [', '.yaml', 'E001'),
    ('canvas: {width: 2, width: 3, height: 2}', '.yaml', 'E001'),
    ('{"canvas":{"width":2,"width":3,"height":2}}', '.json', 'E001'),
    ('canvas: &c {width: 2, height: 2}\nother: *c', '.yaml', 'E001'),
    ('!!python/object/apply:os.system ["echo unsafe"]', '.yaml', 'E001'),
    ('canvas: {width: 2, height: 2}\nsurprise: 1', '.yaml', 'E002'),
    ('canvas: {width: 2, height: 2}\nlayers: [{name: a, operations: [{blur: {}}]}]', '.yaml', 'E014'),
    ('canvas: {width: 2, height: 2}\n', '.txt', 'E001'),
    ('[]', '.yaml', 'E002'),
])
def test_load_reports_structured_errors(tmp_path, source, suffix, code):
    path = tmp_path / ('bad' + suffix)
    path.write_text(source)
    with pytest.raises(AssetError) as exc:
        load_asset(path)
    assert exc.value.result.errors[0].code == code
    assert not exc.value.result.valid


def test_error_has_source_path_and_bad_value(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text('canvas: {width: 3, height: 3}\nlayers:\n- name: a\n'
                    '  operations:\n  - pixel: {at: [1.5, 0], color: red}\n')
    with pytest.raises(AssetError) as exc:
        load_asset(path)
    issue = exc.value.result.errors[0]
    assert issue.path == "layers[0].operations[0].pixel.at[0]"
    assert issue.value == 1.5


def test_unknown_operation_and_multiple_keys_are_rejected():
    for op in ({"blur": {}}, {"pixel": {}, "line": {}}):
        with pytest.raises(ValueError):
            Asset.model_validate({"canvas": {"width": 2, "height": 2},
                                  "layers": [{"name": "a", "operations": [op]}]})


def test_palette_resolves_exact_rgba():
    palette = {"ink": "#aBcDeF", "ghost": "#11223340"}
    assert resolve_color("ink", palette) == (171, 205, 239, 255)
    assert resolve_color("ghost", palette) == (17, 34, 51, 64)
    assert resolve_color("#00000000", palette) == (0, 0, 0, 0)
    for color in ("missing", "#123", "#nothex"):
        with pytest.raises(ValueError):
            resolve_color(color, palette)


def test_missing_input_is_structured(tmp_path):
    with pytest.raises(AssetError) as exc:
        load_asset(tmp_path / "missing.yaml")
    assert exc.value.result.errors[0].code == "E000"
