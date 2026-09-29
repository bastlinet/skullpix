import pytest

from skullpix import Asset, AssetError, lint_asset, resolve_frame, validate_asset


def animation_asset(*, frames=None, animations=None, layers=None, constraints=None):
    return Asset.model_validate({
        "canvas": {"width": 5, "height": 5},
        "palette": {"ink": "#112233", "red": "#ff0000"},
        "layers": layers if layers is not None else [{
            "name": "body", "operations": [{"pixel": {"at": [1, 1], "color": "ink"}}],
            "transform": {"mirror_x": True},
        }],
        "frames": frames or {},
        "animations": animations or {},
        "constraints": constraints or {},
    })


def test_named_frame_inherits_base_layers_without_copies():
    asset = animation_asset(frames={"idle_0": {}})
    resolved = resolve_frame(asset, "idle_0")
    assert resolved.canvas == asset.canvas
    assert resolved.layers == asset.layers
    assert resolved is not asset
    assert resolved.layers is not asset.layers


def test_multilevel_inheritance_merges_only_specified_transform_fields():
    asset = animation_asset(frames={
        "base": {},
        "up": {"extends": "base", "overrides": {"body": {
            "transform": {"translate": [0, -1]}}}},
        "other": {"extends": "up", "overrides": {"body": {
            "transform": {"mirror_y": True}}}},
    })
    base = resolve_frame(asset, "base").layers[0]
    up = resolve_frame(asset, "up").layers[0]
    other = resolve_frame(asset, "other").layers[0]
    assert base.transform.translate == (0, 0)
    assert up.transform.translate == (0, -1)
    assert up.transform.mirror_x is True
    assert other.transform.translate == (0, -1)
    assert other.transform.mirror_x is True
    assert other.transform.mirror_y is True


def test_operations_replace_instead_of_append_and_visibility_overrides():
    asset = animation_asset(frames={"root": {}, "child": {"extends": "root", "overrides": {
        "body": {"visible": False, "operations": [
            {"pixel": {"at": [2, 2], "color": "red"}}]}}}})
    child = resolve_frame(asset, "child").layers[0]
    assert child.visible is False
    assert len(child.operations) == 1
    assert child.operations[0].params.at == (2, 2)
    assert resolve_frame(asset, "root").layers[0].operations[0].params.at == (1, 1)


def test_empty_operations_override_clears_only_the_child_layer():
    asset = animation_asset(frames={"root": {}, "child": {"extends": "root", "overrides": {
        "body": {"operations": []}}}})
    assert resolve_frame(asset, "child").layers[0].operations == []
    assert len(resolve_frame(asset, "root").layers[0].operations) == 1
    assert len(asset.layers[0].operations) == 1


def test_resolved_frame_mutation_cannot_change_parent_or_source():
    asset = animation_asset(frames={"root": {}, "child": {"extends": "root"}})
    one = resolve_frame(asset, "child")
    one.layers[0].operations.clear()
    assert len(resolve_frame(asset, "child").layers[0].operations) == 1
    assert len(resolve_frame(asset, "root").layers[0].operations) == 1
    assert len(asset.layers[0].operations) == 1


def test_resolved_asset_is_standalone_and_does_not_reinterpret_other_roots():
    asset = Asset.model_validate({
        "canvas": {"width": 2, "height": 2},
        "layers": [{"name": "p", "operations": [
            {"pixel": {"at": [0, 0], "color": "#ff0000"}}]}],
        "frames": {
            "a": {"overrides": {"p": {"operations": [
                {"pixel": {"at": [1, 1], "color": "#ff0000"}}]}}},
            "b": {"overrides": {"p": {"transform": {"translate": [1, 0]}}}},
        },
        "animations": {"idle": {"fps": 8, "frames": ["a", "b"]}},
    })
    assert validate_asset(asset).valid
    resolved = resolve_frame(asset, "a")
    assert validate_asset(resolved).valid
    assert resolved.frames == {}
    assert resolved.animations == {}


@pytest.mark.parametrize("frames,code,path", [
    ({"child": {"extends": "missing"}}, "E050", "frames.child.extends"),
    ({"a": {"extends": "b"}, "b": {"extends": "a"}}, "E051", "frames.b.extends"),
    ({"a": {"overrides": {"wrong": {"visible": False}}}}, "E052", "frames.a.overrides.wrong"),
])
def test_bad_inheritance_and_target_have_stable_diagnostics(frames, code, path):
    asset = animation_asset(frames=frames)
    issue = validate_asset(asset).errors[0]
    assert (issue.code, issue.path) == (code, path)
    with pytest.raises(AssetError):
        resolve_frame(asset, next(iter(frames)))


def test_long_flat_inheritance_chain_resolves_without_python_recursion():
    frames = {f"f{index}": {"extends": f"f{index + 1}"} for index in range(1100)}
    frames["f1100"] = {}
    asset = animation_asset(frames=frames)
    assert resolve_frame(asset, "f0").layers[0].name == "body"


def test_long_inheritance_cycle_reports_structured_error():
    frames = {f"f{index}": {"extends": f"f{index + 1}"} for index in range(1100)}
    frames["f1100"] = {"extends": "f0"}
    asset = animation_asset(frames=frames)
    with pytest.raises(AssetError) as exc:
        resolve_frame(asset, "f0")
    assert (exc.value.result.errors[0].code, exc.value.result.errors[0].path) == (
        "E051", "frames.f1100.extends")


def test_duplicate_base_layer_is_ambiguous_override_target():
    layer = {"name": "body", "operations": []}
    asset = animation_asset(layers=[layer, layer], frames={"idle": {
        "overrides": {"body": {"visible": False}}}})
    errors = validate_asset(asset).errors
    assert any(issue.code == "E056" and issue.path == "frames.idle.overrides.body" for issue in errors)


def test_animation_explicit_order_can_repeat_frame_names():
    asset = animation_asset(frames={"a": {}, "b": {}}, animations={"idle": {
        "fps": 8, "loop": False, "frames": ["b", "a", "b"]}})
    assert asset.animations["idle"].frames == ["b", "a", "b"]
    assert asset.animations["idle"].loop is False
    assert validate_asset(asset).valid


def test_unknown_animation_reference_reports_list_index():
    asset = animation_asset(frames={"a": {}}, animations={"idle": {
        "fps": 8, "frames": ["a", "missing"]}})
    issue = validate_asset(asset).errors[0]
    assert (issue.code, issue.path, issue.value) == (
        "E053", "animations.idle.frames[1]", "missing")


@pytest.mark.parametrize("fps", [0, -1, 1.5, "8", True, 1001])
def test_invalid_fps_fails_schema(fps):
    with pytest.raises(ValueError):
        animation_asset(frames={"a": {}}, animations={"idle": {"fps": fps, "frames": ["a"]}})


def test_empty_animation_fails_schema():
    with pytest.raises(ValueError):
        animation_asset(frames={"a": {}}, animations={"idle": {"fps": 8, "frames": []}})


def test_unknown_frame_requested_from_api():
    with pytest.raises(AssetError) as exc:
        resolve_frame(animation_asset(frames={"a": {}}), "missing")
    assert exc.value.result.errors[0].code == "E050"


def test_override_color_reports_editable_source_path_and_suggestion():
    asset = animation_asset(frames={"idle_0": {}, "idle_1": {"extends": "idle_0", "overrides": {
        "body": {"operations": [{"pixel": {"at": [1, 1], "color": "ikn"}}]}}}})
    issue = validate_asset(asset).errors[0]
    assert (issue.code, issue.path, issue.value) == (
        "E012", "frames.idle_1.overrides.body.operations[0].pixel.color", "ikn")
    assert issue.suggestions == ("ink",)


def test_override_transform_clipping_reports_editable_path():
    asset = animation_asset(frames={"off": {"overrides": {"body": {
        "transform": {"translate": [2, 0]}}}}})
    issue = validate_asset(asset).errors[0]
    assert (issue.code, issue.path) == ("E020", "frames.off.overrides.body.transform")


def test_animated_lint_checks_each_resolved_frame_and_global_palette_usage():
    asset = animation_asset(layers=[{"name": "body", "operations": []}], frames={
        "a": {"overrides": {"body": {"operations": [
            {"pixel": {"at": [1, 1], "color": "ink"}}]}}},
        "b": {"overrides": {"body": {"operations": [
            {"pixels": {"points": [[1, 1], [4, 4]], "color": "red"}}]}}},
    })
    result = lint_asset(asset)
    assert result.valid
    assert not any(i.code == "W002" for i in result.issues)
    assert any(i.code == "W003" and i.path == "frames.a" for i in result.issues)
    assert any(i.code == "W004" and i.path == "frames.b" for i in result.issues)


def test_max_colors_is_checked_for_each_frame():
    asset = animation_asset(layers=[{"name": "body", "operations": []}],
                            frames={"a": {"overrides": {"body": {"operations": [
                                {"pixels": {"points": [[1, 1], [2, 1]], "color": "ink"}},
                                {"pixel": {"at": [2, 1], "color": "red"}},
                            ]}}}}, constraints={"max_colors": 1})
    assert any(i.code == "E030" and i.path.startswith("frames.a")
               for i in validate_asset(asset).errors)
