"""Regression tests for malformed inputs that previously escaped diagnostics."""

import json
import os
import subprocess
import sys

import pytest
from typer.testing import CliRunner

from skullpix import AssetError, load_asset
from skullpix.cli import app


@pytest.mark.parametrize("scalar", ["!!int ''", "!!timestamp bad", "!!float ''", "!!bool invalid"])
def test_malformed_yaml_scalars_always_return_json(tmp_path, scalar):
    path = tmp_path / "bad.yaml"
    path.write_text(f"canvas: {{width: {scalar}, height: 1}}\n")
    result = CliRunner().invoke(app, ["validate", str(path), "--json"])
    assert result.exit_code == 1
    assert json.loads(result.stdout)["errors"][0]["code"] == "E001"
    assert "Traceback" not in result.output


@pytest.mark.parametrize("value", ["!!set {red: null, green: null, blue: null}",
                                  "!!binary YWJj", "2026-09-29"])
def test_non_json_yaml_types_rejected(tmp_path, value):
    path = tmp_path / "bad.yaml"
    path.write_text(f"canvas: {{width: 2, height: 2}}\nextra: {value}\n")
    with pytest.raises(AssetError) as exc:
        load_asset(path)
    assert exc.value.result.errors[0].code == "E001"


def test_set_error_diagnostics_are_stable_across_processes(tmp_path):
    path = tmp_path / "bad.yaml"
    path.write_text("canvas: {width: 2, height: 2}\nextra: !!set {red: null, blue: null, green: null}\n")
    outputs = []
    for seed in ("1", "42"):
        result = subprocess.run([sys.executable, "-m", "skullpix", "validate", str(path), "--json"],
                                capture_output=True, text=True,
                                env={**os.environ, "PYTHONHASHSEED": seed})
        assert result.returncode == 1
        outputs.append(result.stdout)
    assert outputs[0] == outputs[1]
    assert json.loads(outputs[0])["errors"][0]["code"] == "E001"


@pytest.mark.parametrize("suffix", [".json", ".yaml"])
def test_deep_input_cannot_overflow_diagnostic_serialization(tmp_path, suffix):
    path = tmp_path / ("deep" + suffix)
    # Hand-written nesting bypasses json.dumps's own recursion limit.
    path.write_text('{"canvas":{"width":1,"height":1},"extra":' + '[' * 600 + '0' + ']' * 600 + '}')
    result = CliRunner().invoke(app, ["validate", str(path), "--json"])
    assert result.exit_code == 1
    data = json.loads(result.stdout)
    assert data["valid"] is False
    assert data["errors"][0]["code"] == "E001"
