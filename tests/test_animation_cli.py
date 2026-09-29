import json

from PIL import Image
import pytest
from typer.testing import CliRunner

from skullpix.cli import app

runner = CliRunner()


@pytest.fixture
def animated_source(tmp_path):
    path = tmp_path / "animated.yaml"
    path.write_text('''version: 1
canvas: {width: 3, height: 2, background: clear}
palette: {clear: "#00000000", ink: "#112233"}
layers:
  - name: body
    operations: [{pixel: {at: [0, 0], color: ink}}]
frames:
  a: {}
  b:
    extends: a
    overrides:
      body:
        transform: {translate: [1, 0]}
animations:
  idle: {fps: 8, loop: true, frames: [b, a, b]}
''')
    return path


def test_cli_frame_sheet_metadata_preview_and_default_render(animated_source):
    output = animated_source.parent / "b.png"
    result = runner.invoke(app, ["render", str(animated_source), "--frame", "b", "-o", str(output)])
    assert result.exit_code == 0, result.output
    assert Image.open(output).getpixel((1, 0)) == (17, 34, 51, 255)
    base = animated_source.parent / "base.png"
    assert runner.invoke(app, ["render", str(animated_source), "-o", str(base)]).exit_code == 0
    assert Image.open(base).getpixel((0, 0)) == (17, 34, 51, 255)
    sheet = animated_source.parent / "sub" / "idle.png"
    metadata = animated_source.parent / "sub" / "idle.json"
    result = runner.invoke(app, ["sheet", str(animated_source), "--animation", "idle", "-o", str(sheet),
                                 "--metadata", str(metadata), "--json"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["valid"] is True
    assert Image.open(sheet).size == (9, 2)
    assert json.loads(metadata.read_bytes())["frames"][2]["x"] == 6
    first_png, first_json = sheet.read_bytes(), metadata.read_bytes()
    result = runner.invoke(app, ["sheet", str(animated_source), "--animation", "idle", "-o", str(sheet),
                                 "--metadata", str(metadata)])
    assert result.exit_code == 0, result.output
    assert (sheet.read_bytes(), metadata.read_bytes()) == (first_png, first_json)
    preview = animated_source.parent / "idle.gif"
    result = runner.invoke(app, ["preview", str(animated_source), "--animation", "idle", "-o", str(preview)])
    assert result.exit_code == 0, result.output
    assert Image.open(preview).n_frames == 3


@pytest.mark.parametrize("command,arguments,code", [
    ("render", ["--frame", "unknown"], "E050"),
    ("sheet", ["--animation", "unknown"], "E057"),
    ("preview", ["--animation", "unknown"], "E057"),
])
def test_cli_unknown_selectors_report_json(animated_source, command, arguments, code):
    result = runner.invoke(app, [command, str(animated_source), *arguments, "--json"])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["errors"][0]["code"] == code


@pytest.mark.parametrize("change,code,path", [
    ('fps: 0', "E055", "animations.idle.fps"),
    ('frames: []', "E054", "animations.idle.frames"),
])
def test_cli_invalid_animation_schema_has_specific_code(animated_source, change, code, path):
    source = animated_source.read_text()
    source = source.replace("fps: 8", change) if "fps" in change else source.replace("frames: [b, a, b]", change)
    animated_source.write_text(source)
    result = runner.invoke(app, ["validate", str(animated_source), "--json"])
    assert result.exit_code == 1
    issue = json.loads(result.stdout)["errors"][0]
    assert (issue["code"], issue["path"]) == (code, path)


def test_cli_invalid_override_reports_source_location(animated_source):
    animated_source.write_text(animated_source.read_text().replace("body:\n        transform", "missing:\n        transform"))
    result = runner.invoke(app, ["lint", str(animated_source), "--json"])
    assert result.exit_code == 1
    issue = json.loads(result.stdout)["errors"][0]
    assert (issue["code"], issue["path"]) == ("E052", "frames.b.overrides.missing")


def test_sheet_output_error_does_not_replace_input(animated_source):
    before = animated_source.read_bytes()
    result = runner.invoke(app, ["sheet", str(animated_source), "--animation", "idle",
                                 "-o", str(animated_source), "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["errors"][0]["code"] == "E040"
    assert animated_source.read_bytes() == before


def test_duplicate_frame_identifier_is_rejected_by_parser(animated_source):
    animated_source.write_text(animated_source.read_text().replace("  b:\n", "  a: {}\n  b:\n"))
    result = runner.invoke(app, ["validate", str(animated_source), "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["errors"][0]["code"] == "E001"


@pytest.mark.parametrize("old,new,code,path", [
    ("extends: a", "extends: absent", "E050", "frames.b.extends"),
    ("a: {}", "a: {extends: b}", "E051", "frames.b.extends"),
    ("frames: [b, a, b]", "frames: [b, unknown, b]", "E053", "animations.idle.frames[1]"),
])
def test_validate_json_animation_reference_errors(animated_source, old, new, code, path):
    animated_source.write_text(animated_source.read_text().replace(old, new))
    result = runner.invoke(app, ["validate", str(animated_source), "--json"])
    assert result.exit_code == 1
    assert any((issue["code"], issue["path"]) == (code, path)
               for issue in json.loads(result.stdout)["errors"])


def test_cli_long_inheritance_cycle_is_structured(animated_source):
    frames = {f"f{index}": {"extends": f"f{index + 1}"} for index in range(1100)}
    frames["f1100"] = {"extends": "f0"}
    source = animated_source.with_suffix(".json")
    source.write_text(json.dumps({"canvas": {"width": 1, "height": 1}, "frames": frames}))
    result = runner.invoke(app, ["render", str(source), "--frame", "f0", "--json"])
    assert result.exit_code == 1
    issue = json.loads(result.stdout)["errors"][0]
    assert (issue["code"], issue["path"]) == ("E051", "frames.f1100.extends")


def test_animated_json_source_uses_same_models(animated_source):
    import yaml

    data = yaml.safe_load(animated_source.read_text())
    target = animated_source.with_suffix(".json")
    target.write_text(json.dumps(data))
    result = runner.invoke(app, ["validate", str(target), "--json"])
    assert result.exit_code == 0, result.output
