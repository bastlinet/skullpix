from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from skullpix import lint_asset, load_asset, png_bytes, render_asset, validate_asset

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("name", ["skull", "frog", "sword"])
def test_examples_match_reviewed_golden_hashes(name):
    asset = load_asset(ROOT / "examples" / f"{name}.yaml")
    assert validate_asset(asset).valid
    assert lint_asset(asset).valid
    first = png_bytes(render_asset(asset, strict=True))
    assert first == png_bytes(render_asset(asset, strict=True))
    hashes = json.loads((ROOT / "tests" / "golden_sha256.json").read_text())
    assert sha256(first).hexdigest() == hashes[f"{name}.png"]


def test_separate_processes_and_hash_seeds_produce_identical_png(tmp_path):
    outputs = []
    for seed in ("1", "729"):
        output = tmp_path / f"{seed}.png"
        subprocess.run([sys.executable, "-m", "skullpix", "render", str(ROOT / "examples" / "skull.yaml"),
                        "-o", str(output), "--strict"], check=True, capture_output=True,
                       env={**os.environ, "PYTHONHASHSEED": seed})
        outputs.append(output.read_bytes())
    assert outputs[0] == outputs[1]
