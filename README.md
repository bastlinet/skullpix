# Skullpix

Skullpix is a deterministic, headless pixel-art compiler designed for humans and AI coding agents.

Pixel art is authored as YAML/JSON source and compiled into raster assets.

```sh
pip install -e .
skullpix render examples/skull.yaml
```

Requires Python 3.12+. There is no GUI, model API or game-engine dependency.

```yaml
version: 1
canvas:
  width: 8
  height: 8
  background: transparent
palette:
  transparent: "#00000000"
  outline: "#21182f"
  bone: "#e1d6e8"
layers:
  - name: skull
    operations:
      - ellipse:
          box: [2, 1, 4, 4]
          color: bone
      - outline:
          color: outline
          connectivity: 8
      - pixels:
          color: outline
          points: [[3, 3], [5, 3]]
```

Traditional pixel-art editors are optimized for interactive human workflows.
Skullpix treats graphics as source code:

```text
LLM / human → spec → validate → render → test → commit
```

This allows coding agents to safely modify graphical assets using normal
software-development workflows. The YAML/JSON file is the source of truth;
PNG files are build outputs.

## Commands

```sh
skullpix validate examples/skull.yaml
skullpix render examples/skull.yaml -o build/skull.png --strict
skullpix lint examples/skull.yaml
skullpix inspect examples/skull.yaml --json
skullpix --version
```

| Command | Behavior |
| --- | --- |
| `render INPUT [-o OUTPUT] [--strict] [--json]` | Write PNG; default output replaces the source extension with `.png`. Create missing output directories. |
| `validate INPUT [--json]` | Check parsing, schema, colors, names, coordinates, transforms and constraints. |
| `lint INPUT [--json] [--no-strict] [--no-off-palette]` | Validate and report unused/off-palette colors, isolated pixels, components and used-color count. |
| `inspect INPUT [--json]` | Validate and report dimensions, layers, operations, colors and pixel counts. |

Exit codes: **0** for success (including lint warnings), **1** for input,
validation or output errors, **2** for CLI usage errors. JSON mode writes one
JSON object to stdout. Usage errors such as a missing argument remain Typer
usage messages on stderr. `python -m skullpix` also works.

Validation, inspection and lint reject out-of-bounds drawing by default.
Rendering clips and reports `W020` unless `--strict` is set. Other errors,
including `max_colors`, always prevent rendering. Failed validation leaves an
existing output untouched; successful output is written atomically.

Example validation error (additional diagnostic fields omitted here):

```json
{
  "valid": false,
  "errors": [{
    "code": "E012",
    "path": "layers[1].operations[3].pixels.color",
    "value": "bonelight",
    "message": "Palette has no color named 'bonelight'.",
    "suggestions": ["bone_light"]
  }]
}
```

## Format and pixel semantics

See the [complete v1 format](docs/format.md) for operation examples and diagnostics.

- Coordinates are integers: `(0, 0)` is top-left, x increases right, y down.
  Floats, booleans and numeric strings are rejected.
- Every box is **`[x, y, width, height]`**. Right/bottom edges are exclusive;
  `[2, 3, 1, 1]` covers exactly pixel `(2, 3)`.
- Operations write exact RGBA to their own transparent layer. Later layers
  composite on top, in declaration order. No anti-aliasing or interpolation.
- Palette names are preferred. Quoted `#RRGGBB` and `#RRGGBBAA` are accepted.
  A pixel with alpha greater than zero counts as occupied.
- Layer transforms apply in this order: `mirror_x`, `mirror_y`, clockwise
  `rotate`, `translate`. `mirror_x` flips left/right; `mirror_y` flips top/bottom.
- `constraints: {max_colors: 16}` limits distinct **occupied RGBA colors in the
  final composite**, including colors created by alpha blending.

## Python API

```python
from skullpix import load_asset, render_asset, validate_asset, save_png

asset = load_asset("examples/skull.yaml")
result = validate_asset(asset)
if not result.valid:
    raise ValueError(result.to_dict())

image = render_asset(asset, strict=True)  # fresh Pillow RGBA image
image.save("skull-pillow.png")           # ordinary Pillow save is available
save_png(image, "build/skull.png")      # canonical, byte-stable Skullpix encoder
```

Also exported: `Asset`, `AssetError`, `Issue`, `ValidationResult`, `lint_asset`,
`inspect_asset`, `png_bytes`. `Asset.model_validate(data)` accepts a Python
mapping. `Asset.model_json_schema()` exposes the authoring schema.

`load_asset` validates syntax/schema and raises `AssetError` with `.result` for
structured diagnostics. `validate_asset` checks a loaded model's semantics and
returns a result. `render_asset` raises `AssetError` on errors; relaxed clipping
emits Python `UserWarning` messages. The API never invokes the CLI or reads
configuration, environment variables or network services.

## Determinism and tests

The CLI and `save_png` use a canonical RGBA8 PNG encoding: fixed filter-zero
scanlines, stored DEFLATE blocks, only IHDR/IDAT/IEND chunks. No timestamps,
text, profiles or other metadata are written. PNG bytes do not depend on the
zlib compression version. The tradeoff is larger PNGs: roughly four bytes per
pixel. Pillow's raster version is pinned in `pyproject.toml`; all development
dependencies are locked in `uv.lock`.

The byte guarantee applies to the canonical encoder. Calling Pillow's own
`image.save` bypasses that encoder and depends on the caller's Pillow/zlib stack.

```sh
# Reproduce the development environment:
uv sync --frozen
uv run pytest

# Or use pip in an activated Python 3.12+ virtual environment:
pip install -e '.[test]'
pytest

skullpix render examples/skull.yaml -o /tmp/skull-a.png
skullpix render examples/skull.yaml -o /tmp/skull-b.png
cmp /tmp/skull-a.png /tmp/skull-b.png
```

Tests assert literal pixel matrices, alpha values, error paths, CLI JSON and
exit codes. [Golden SHA-256 values](tests/golden_sha256.json) cover all three
examples; subprocess tests vary Python hash seeds. Only update golden hashes
after deliberately changing raster semantics, checking the rendered examples,
and considering the Skullpix version. Never regenerate them as part of tests.

The [skull](examples/skull.yaml) demonstrates ellipses, pixels, outlines and
layers; the [frog](examples/frog.yaml) adds asymmetry, eyes and a layer
translation; the [sword](examples/sword.yaml) uses polygons and lines.

## Architecture

```text
skullpix/
  schema.py          strict Pydantic authoring models
  parsing.py         safe YAML/JSON; duplicate keys rejected
  palette.py         exact color resolution
  operations/        primitives, fill, outline, transforms
  renderer.py        independent layer rendering and composition
  validation/        semantic checks and optional lint advice
  inspection.py      stable asset statistics
  diagnostics.py     shared error/warning contract
  png.py             canonical PNG bytes and atomic save
  cli.py             Typer command adapters
```

## Non-goals for v0.1

- No GUI, painting UI or Aseprite clone.
- No vector graphics, arbitrary subpixel coordinates or arbitrary-angle rotation.
- No anti-aliased rendering or Photoshop-style filters.
- No AI image generation, image-generation model dependency or embedded LLM APIs.
- No game-engine dependency or Godot dependency.
- No proprietary formats, raster import, animation, spritesheets or tilesets.

Skullpix is an independent implementation built on general raster primitives.
No implementation code was copied from Aseprite, LibreSprite or other editors.

## Limits and future direction

v0.1 compiles a single canvas. YAML aliases/includes, reusable components,
variables and imported images are unsupported. Canvas dimensions are at most
4096 per axis; coordinates are within −65536…65536, box sizes within 1…65536;
source files are limited to 4 MiB. Large flood fills and lint scans are CPU
work proportional to canvas area. This is a local tool, not a sandbox for
adversarial public uploads.

For **v0.2**, keep the scope to named frames, animation tags/timing, deterministic
spritesheet packing and JSON metadata. Existing `Layer` and operation models
can be reused inside a future `frames` container; `version` provides an explicit
format migration boundary. See [future format notes](docs/future.md).

Later candidates include tileset constraints, indexed palettes, reusable
components, deterministic noise, controlled dithering, edge highlights,
visual regression tools, optional Godot resource export, and Aseprite or
Pixelorama adapters. None is implemented in v0.1.

## License

[MIT](LICENSE).
