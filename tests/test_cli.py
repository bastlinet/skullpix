import json

import pytest
from PIL import Image
from typer.testing import CliRunner

from skullpix.cli import app

runner = CliRunner()


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "sprite.yaml"
    path.write_text('canvas: {width: 3, height: 3}\npalette: {ink: "#112233"}\n'
                    'layers: [{name: main, operations: [{pixel: {at: [1, 1], color: ink}}]}]\n')
    return path


def test_render_default_output_and_explicit_directory(source):
    result = runner.invoke(app, ["render", str(source)])
    assert result.exit_code == 0, result.output
    first = source.with_suffix(".png")
    assert Image.open(first).getpixel((1, 1)) == (17, 34, 51, 255)
    second = source.parent / "build" / "custom.png"
    assert runner.invoke(app, ["render", str(source), "-o", str(second)]).exit_code == 0
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize("command", ["validate", "lint"])
def test_validation_json_and_warning_exit(source, command):
    result = runner.invoke(app, [command, str(source), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert data["valid"] is True
    assert data["errors"] == []
    if command == "lint":
        assert data["warnings"][0]["code"] == "W003"


def test_inspect_json_and_text(source):
    result = runner.invoke(app, ["inspect", str(source), "--json"])
    assert result.exit_code == 0, result.output
    stats = json.loads(result.stdout)
    assert stats["occupied_pixels"] == 1
    assert stats["transparent_pixels"] == 8
    assert stats["used_colors"] == 1
    result = runner.invoke(app, ["inspect", str(source)])
    assert "Canvas: 3x3\nLayers: 1\nOperations: 1" in result.stdout


@pytest.mark.parametrize("command", ["render", "validate", "lint", "inspect"])
@pytest.mark.parametrize("contents,code", [
    ('canvas: [', 'E001'),
    ('canvas: {width: 0, height: 3}', 'E002'),
    ('canvas: {width: .nan, height: 3}', 'E002'),
    ('canvas: {width: 3, height: 3}\nlayers: [{name: a, operations: [{pixel: {at: [0, 0], color: nope}}]}]', 'E012'),
])
def test_errors_are_json_with_failure_exit(source, command, contents, code):
    source.write_text(contents)
    result = runner.invoke(app, [command, str(source), "--json"])
    assert result.exit_code == 1, result.output
    data = json.loads(result.stdout, parse_constant=lambda value: pytest.fail(f"Non-JSON constant {value}"))
    assert data["valid"] is False
    assert data["errors"][0]["code"] == code
    assert "Traceback" not in result.output


def test_render_strict_does_not_touch_existing_output(source):
    source.write_text('canvas: {width: 3, height: 3}\nlayers: [{name: a, operations: [{pixel: {at: [3, 0], color: "#123456"}}]}]')
    output = source.with_suffix(".png")
    output.write_bytes(b"keep existing output")
    result = runner.invoke(app, ["render", str(source), "--strict"])
    assert result.exit_code == 1
    assert "E020" in result.output
    assert output.read_bytes() == b"keep existing output"
    result = runner.invoke(app, ["render", str(source)])
    assert result.exit_code == 0
    assert "W020" in result.stderr
    assert Image.open(output).size == (3, 3)


def test_lint_strictness_and_off_palette_switches(source):
    source.write_text('canvas: {width: 3, height: 3}\nlayers: [{name: a, operations: [{pixel: {at: [3, 0], color: "#123456"}}]}]')
    assert runner.invoke(app, ["lint", str(source)]).exit_code == 1
    result = runner.invoke(app, ["lint", str(source), "--no-strict", "--no-off-palette", "--json"])
    assert result.exit_code == 0
    assert [w["code"] for w in json.loads(result.stdout)["warnings"]] == ["W020"]


@pytest.mark.parametrize("command", ["render", "validate", "lint", "inspect"])
def test_missing_file_is_structured(tmp_path, command):
    result = runner.invoke(app, [command, str(tmp_path / "missing.yaml"), "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["errors"][0]["code"] == "E000"


def test_output_error_is_structured(source):
    obstacle = source.parent / "file"
    obstacle.write_text("not a directory")
    result = runner.invoke(app, ["render", str(source), "-o", str(obstacle / "out.png"), "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["errors"][0]["code"] == "E040"


def test_render_cannot_overwrite_source(source):
    before = source.read_bytes()
    result = runner.invoke(app, ["render", str(source), "-o", str(source), "--json"])
    assert result.exit_code == 1
    assert source.read_bytes() == before


def test_help_and_version():
    assert runner.invoke(app, ["--help"]).exit_code == 0
    assert runner.invoke(app, ["--version"]).stdout.strip() == "0.3.0"
