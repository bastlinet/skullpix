"""Regression cases confirmed by the Astra/Opus review of v0.2."""

from io import BytesIO
import json

from PIL import Image
import pytest
from typer.testing import CliRunner

from skullpix import (
    Asset, AssetError, inspect_asset, load_asset, preview_bytes, render_asset,
    render_frame, resolve_frame,
)
from skullpix.cli import app


def test_override_operations_and_nested_points_are_isolated():
    asset = Asset.model_validate({
        "canvas": {"width": 2, "height": 2},
        "layers": [{"name": "p"}],
        "frames": {
            "a": {"overrides": {"p": {"operations": [
                {"pixels": {"points": [[0, 0]], "color": "#ff0000"}}]}}},
            "b": {"extends": "a"},
        },
    })
    resolved = resolve_frame(asset, "a")
    resolved.layers[0].operations[0].params.points.append((1, 1))
    resolved.layers[0].operations.clear()
    original = asset.frames["a"].overrides["p"].operations
    assert len(original) == 1
    assert original[0].params.points == [(0, 0)]
    assert resolve_frame(asset, "b").layers[0].operations[0].params.points == [(0, 0)]


@pytest.mark.parametrize("render", [render_asset, inspect_asset, lambda a: render_frame(a, "ok")])
def test_public_rendering_checks_unused_frame_references(render):
    asset = Asset.model_validate({"canvas": {"width": 1, "height": 1},
                                 "frames": {"ok": {}, "bad": {"extends": "missing"}}})
    with pytest.raises(AssetError) as exc:
        render(asset)
    assert exc.value.result.errors[0].path == "frames.bad.extends"


def test_frame_api_reports_override_source_path():
    asset = Asset.model_validate({
        "canvas": {"width": 2, "height": 2}, "layers": [{"name": "p"}],
        "frames": {"a": {"overrides": {"p": {"operations": [
            {"pixel": {"at": [0, 0], "color": "missing"}}]}}}},
    })
    with pytest.raises(AssetError) as exc:
        render_frame(asset, "a")
    assert exc.value.result.errors[0].path == "frames.a.overrides.p.operations[0].pixel.color"


def test_preview_does_not_require_a_one_row_sheet():
    asset = Asset.model_validate({"canvas": {"width": 4096, "height": 1},
                                 "frames": {"a": {}},
                                 "animations": {"idle": {"fps": 8, "frames": ["a"] * 16}}})
    with Image.open(BytesIO(preview_bytes(asset, "idle"))) as gif:
        assert gif.size == (4096, 1)
        assert gif.n_frames == 16


def test_preview_total_pixel_limit_has_its_own_diagnostic():
    asset = Asset.model_validate({"canvas": {"width": 4096, "height": 4096},
                                 "frames": {"a": {}},
                                 "animations": {"idle": {"fps": 8, "frames": ["a", "a"]}}})
    with pytest.raises(AssetError) as exc:
        preview_bytes(asset, "idle")
    assert exc.value.result.errors[0].code == "E060"


@pytest.mark.parametrize("frames", ["a", None, 1, {}, True])
def test_wrong_type_animation_list_is_a_schema_error(tmp_path, frames):
    source = tmp_path / "bad.json"
    source.write_text(json.dumps({"canvas": {"width": 1, "height": 1},
                                  "animations": {"idle": {"fps": 8, "frames": frames}}}))
    with pytest.raises(AssetError) as exc:
        load_asset(source)
    assert exc.value.result.errors[0].code == "E002"


def test_cli_base_render_rejects_invalid_unused_frames(tmp_path):
    source = tmp_path / "bad.json"
    source.write_text(json.dumps({"canvas": {"width": 1, "height": 1},
                                  "frames": {"bad": {"extends": "missing"}}}))
    result = CliRunner().invoke(app, ["render", str(source), "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["errors"][0]["code"] == "E050"


def test_metadata_write_error_names_metadata_destination(tmp_path):
    source = tmp_path / "asset.json"
    source.write_text(json.dumps({"canvas": {"width": 1, "height": 1}, "frames": {"a": {}},
                                  "animations": {"idle": {"fps": 8, "frames": ["a"]}}}))
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("occupied")
    metadata = blocker / "idle.json"
    result = CliRunner().invoke(app, ["sheet", str(source), "--animation", "idle",
                                     "--metadata", str(metadata), "--json"])
    assert result.exit_code == 1
    issue = json.loads(result.stdout)["errors"][0]
    assert (issue["path"], issue["value"]) == ("metadata", str(metadata))


@pytest.mark.parametrize("command", ["sheet", "preview"])
def test_export_success_json_preserves_diagnostic_envelope(tmp_path, command):
    source = tmp_path / "asset.json"
    source.write_text(json.dumps({"canvas": {"width": 1, "height": 1}, "frames": {"a": {}},
                                  "animations": {"idle": {"fps": 8, "frames": ["a"]}}}))
    result = CliRunner().invoke(app, [command, str(source), "--animation", "idle", "--json"])
    assert result.exit_code == 0
    assert {key: json.loads(result.stdout)[key] for key in ("valid", "errors", "warnings", "info")} == {
        "valid": True, "errors": [], "warnings": [], "info": []}
