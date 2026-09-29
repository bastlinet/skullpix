import pytest

from skullpix import AssetError, lint_asset, render_asset, validate_asset
from skullpix.inspection import inspect_asset


def test_unknown_color_suggestion_path_and_value(make_asset):
    asset = make_asset([{"pixel": {"at": [0, 0], "color": "bonelight"}}],
                       palette={"bone_light": "#dddddd"})
    result = validate_asset(asset)
    issue = result.errors[0]
    assert (issue.code, issue.path, issue.value) == (
        "E012", "layers[0].operations[0].pixel.color", "bonelight")
    assert issue.suggestions == ("bone_light",)
    assert result.to_dict()["valid"] is False
    with pytest.raises(AssetError):
        render_asset(asset)


def test_all_color_fields_are_validated_even_hidden_layers(make_asset):
    asset = make_asset(canvas={"width": 3, "height": 3, "background": "unknown"}, layers=[
        {"name": "hidden", "visible": False, "operations": [
            {"replace_color": {"from": "nope", "to": "other"}},
            {"outline": {"color": "#123"}},
        ]}])
    errors = validate_asset(asset).errors
    assert [e.path for e in errors] == ["canvas.background",
        "layers[0].operations[0].replace_color.from", "layers[0].operations[0].replace_color.to",
        "layers[0].operations[1].outline.color"]
    assert errors[-1].code == "E011"


def test_duplicate_layer_names(make_asset):
    result = validate_asset(make_asset(layers=[{"name": "a"}, {"name": "a"}]))
    assert result.errors[0].code == "E013"
    assert result.errors[0].path == "layers[1].name"


@pytest.mark.parametrize("op", [
    {"pixel": {"at": [-1, 1], "color": "ink"}},
    {"pixels": {"points": [[0, 0], [5, 1]], "color": "ink"}},
    {"line": {"from": [0, 0], "to": [0, 5], "color": "ink"}},
    {"rect": {"box": [4, 4, 2, 1], "color": "ink"}},
    {"ellipse": {"box": [0, -1, 3, 3], "color": "ink"}},
    {"polygon": {"points": [[0, 0], [5, 0], [1, 2]], "color": "ink"}},
    {"fill": {"seed": [0, 5], "color": "ink"}},
])
def test_out_of_bounds_is_error_by_default_and_warning_if_relaxed(make_asset, op):
    asset = make_asset([op])
    assert validate_asset(asset).errors[0].code == "E020"
    assert lint_asset(asset).errors[0].code == "E020"
    relaxed = validate_asset(asset, strict=False)
    assert relaxed.valid
    assert relaxed.warnings[0].code == "W020"
    with pytest.raises(AssetError):
        render_asset(asset, strict=True)
    with pytest.warns(UserWarning, match="W020"):
        render_asset(asset)


def test_outline_bounds_checked_from_actual_pixels(make_asset):
    asset = make_asset([{"pixel": {"at": [0, 0], "color": "ink"}}, {"outline": {"color": "ink"}}])
    errors = validate_asset(asset).errors
    assert len(errors) == 1
    assert errors[0].path == "layers[0].operations[1].outline"


def test_transforms_report_only_lost_occupied_pixels(make_asset):
    layers = [{"name": "a", "transform": {"translate": [1, 0]}, "operations": [
        {"pixel": {"at": [4, 0], "color": "ink"}}]}]
    assert validate_asset(make_asset(layers=layers)).errors[0].path == "layers[0].transform"
    layers[0]["operations"][0]["pixel"]["at"] = [1, 0]
    assert validate_asset(make_asset(layers=layers)).valid


def test_hidden_layer_clipping_is_validated(make_asset):
    asset = make_asset(layers=[{"name": "a", "visible": False, "operations": [
        {"pixel": {"at": [10, 0], "color": "ink"}}]}])
    assert not validate_asset(asset).valid


def test_lint_off_palette_is_optional_and_compares_rgba_values(make_asset):
    asset = make_asset([
        {"pixel": {"at": [1, 1], "color": "#112233FF"}},
        {"pixel": {"at": [1, 2], "color": "#abcdef"}},
    ])
    issues = [i for i in lint_asset(asset).warnings if i.code == "W001"]
    assert len(issues) == 1
    assert issues[0].path.endswith("operations[1].pixel.color")
    assert not any(i.code == "W001" for i in lint_asset(asset, off_palette=False).issues)


def test_unused_palette_counts_raw_colors_as_use(make_asset):
    asset = make_asset([{"pixel": {"at": [1, 1], "color": "#112233ff"}}])
    unused = [i.value for i in lint_asset(asset).issues if i.code == "W002"]
    assert unused == ["red", "clear"]


def test_isolated_pixels_and_components_are_eight_connected(make_asset):
    asset = make_asset([{"pixels": {"points": [[0, 0], [2, 2], [3, 3]], "color": "ink"}}])
    result = lint_asset(asset)
    singleton = next(i for i in result.warnings if i.code == "W003")
    components = next(i for i in result.warnings if i.code == "W004")
    assert singleton.points == ((0, 0),)
    assert components.value == 2
    assert result.valid


def test_fully_transparent_pixels_are_not_components(make_asset):
    result = lint_asset(make_asset([{"pixel": {"at": [0, 0], "color": "#ff000000"}}]))
    assert not any(i.code in ("W003", "W004") for i in result.issues)


def test_max_colors_counts_composited_nontransparent_rgba(make_asset):
    asset = make_asset(constraints={"max_colors": 1}, size=(2, 1), layers=[
        {"name": "a", "operations": [{"rect": {"box": [0, 0, 2, 1], "color": "red"}}]},
        {"name": "b", "operations": [{"pixel": {"at": [0, 0], "color": "#0000ff80"}}]},
    ])
    result = validate_asset(asset)
    assert result.errors[0].code == "E030"
    assert result.errors[0].value == 2
    with pytest.raises(AssetError):
        render_asset(asset)


def test_inspect_stats_and_lint_color_count(make_asset):
    asset = make_asset([{"pixels": {"points": [[1, 1], [2, 1]], "color": "ink"}}])
    stats = inspect_asset(asset)
    assert stats == {"version": 1, "canvas": {"width": 5, "height": 5}, "layers": 1,
                     "operations": 1, "palette_colors": 3, "used_colors": 1,
                     "transparent_pixels": 23, "occupied_pixels": 2}
    assert next(i for i in lint_asset(asset).issues if i.code == "I001").value == 1
