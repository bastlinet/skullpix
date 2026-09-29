import json
import os
import subprocess
import sys

from PIL import Image
import pytest
from typer.testing import CliRunner

from skullpix.cli import app

runner = CliRunner()


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "tiles.yaml"
    path.write_text('''canvas: {width: 2, height: 3}
palette: {stone: "#112233"}
layers:
  - name: paint
    operations: [{rect: {box: [0, 0, 2, 3], color: stone}}]
frames:
  a: {}
  b: {extends: a}
  c: {extends: b}
tilesets:
  stone:
    columns: 2
    tiles: [c, a, b]
    seams: [{from: a, to: b, axis: x}, {from: b, to: c, axis: y}]
''')
    return path


def test_cli_exports_png_and_metadata_with_stable_json_envelope(source):
    output = source.parent / "nested" / "grid.png"
    metadata = output.with_suffix(".json")
    result = runner.invoke(app, ["tileset", str(source), "--tileset", "stone", "-o", str(output),
                                 "--metadata", str(metadata), "--json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.stdout)
    assert {key: data[key] for key in ("valid", "errors", "warnings", "info")} == {
        "valid": True, "errors": [], "warnings": [], "info": []}
    assert data["tileset"] == json.loads(metadata.read_bytes())
    assert data["tileset"]["tiles"][0]["name"] == "c"
    assert Image.open(output).size == (4, 6)
    assert Image.open(output).getpixel((3, 5)) == (0, 0, 0, 0)


def test_default_destination_and_human_output(source):
    result = runner.invoke(app, ["tileset", str(source), "--tileset", "stone"])
    assert result.exit_code == 0, result.output
    assert "Tileset:" in result.output
    assert source.with_name("tiles-stone.png").is_file()


def test_unknown_tileset_is_json_error(source):
    result = runner.invoke(app, ["tileset", str(source), "--tileset", "stnoe", "--json"])
    assert result.exit_code == 1
    issue = json.loads(result.stdout)["errors"][0]
    assert (issue["code"], issue["path"], issue["suggestions"]) == (
        "E070", "tilesets.stnoe", ["stone"])


@pytest.mark.parametrize("change,code,path", [
    (("columns: 2", "columns: false"), "E074", "tilesets.stone.columns"),
    (("tiles: [c, a, b]", "tiles: []"), "E071", "tilesets.stone.tiles"),
    (("tiles: [c, a, b]", "tiles: [a, a, b]"), "E073", "tilesets.stone.tiles[1]"),
    (("tiles: [c, a, b]", "tiles: [c, a, absent]"), "E072", "tilesets.stone.tiles[2]"),
    (("from: a", "from: absent"), "E075", "tilesets.stone.seams[0].from"),
    (("axis: x", "axis: z"), "E078", "tilesets.stone.seams[0].axis"),
])
def test_validation_errors_are_machine_readable(source, change, code, path):
    source.write_text(source.read_text().replace(*change))
    result = runner.invoke(app, ["validate", str(source), "--json"])
    assert result.exit_code == 1
    assert any((issue["code"], issue["path"]) == (code, path)
               for issue in json.loads(result.stdout)["errors"])


@pytest.mark.parametrize("arguments", [
    ["validate"], ["lint"], ["lint", "--no-strict"], ["render"], ["inspect"],
    ["tileset", "--tileset", "stone"],
])
def test_all_cli_entry_points_report_broken_seams(source, arguments):
    source.write_text(source.read_text().replace('b: {extends: a}', '''b:
    extends: a
    overrides:
      paint:
        operations: [{rect: {box: [0, 0, 2, 3], color: "#ff0000"}}]'''))
    result = runner.invoke(app, [arguments[0], str(source), *arguments[1:], "--json"])
    assert result.exit_code == 1, result.output
    assert any(issue["code"] == "E076" for issue in json.loads(result.stdout)["errors"])


@pytest.mark.parametrize("collision", ["png-source", "metadata-source", "same-output"])
def test_output_aliases_do_not_overwrite_sources_or_outputs(source, collision):
    png, metadata = source.with_suffix(".png"), source.with_name("metadata.json")
    if collision == "png-source":
        png = source
    elif collision == "metadata-source":
        metadata = source
    else:
        metadata = png
    before = source.read_bytes()
    result = runner.invoke(app, ["tileset", str(source), "--tileset", "stone", "-o", str(png),
                                 "--metadata", str(metadata), "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["errors"][0]["code"] == "E040"
    assert source.read_bytes() == before
    if png != source:
        assert not png.exists()


def test_metadata_write_failure_identifies_its_destination(source):
    blocker = source.parent / "blocked"
    blocker.write_text("file")
    metadata = blocker / "atlas.json"
    result = runner.invoke(app, ["tileset", str(source), "--tileset", "stone",
                                 "--metadata", str(metadata), "--json"])
    assert result.exit_code == 1
    issue = json.loads(result.stdout)["errors"][0]
    assert (issue["code"], issue["path"], issue["value"]) == ("E040", "metadata", str(metadata))


def test_separate_processes_and_hash_seeds_produce_identical_atlas_and_json(source):
    outputs = []
    for seed in ("3", "987"):
        png, metadata = source.parent / f"{seed}.png", source.parent / f"{seed}.json"
        subprocess.run([sys.executable, "-m", "skullpix", "tileset", str(source), "--tileset", "stone",
                        "-o", str(png), "--metadata", str(metadata)], check=True, capture_output=True,
                       env={**os.environ, "PYTHONHASHSEED": seed})
        outputs.append((png.read_bytes(), metadata.read_bytes()))
    assert outputs[0] == outputs[1]
