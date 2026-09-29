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
| `render INPUT --frame NAME [-o OUTPUT] [--strict] [--json]` | Render one named frame through the same renderer. |
| `validate INPUT [--json]` | Check parsing, schema, colors, names, coordinates, transforms and constraints. |
| `lint INPUT [--json] [--no-strict] [--no-off-palette]` | Validate and report unused/off-palette colors, isolated pixels, components and used-color count. |
| `inspect INPUT [--json]` | Validate and report dimensions, layers, operations, colors and pixel counts. |
| `sheet INPUT --animation NAME [-o PNG] [--metadata JSON] [--json]` | Export fixed-size cells in explicit animation order. |
| `tileset INPUT --tileset NAME [-o PNG] [--metadata JSON] [--json]` | Export named frames as a row-major grid with declared seam validation. |
| `preview INPUT --animation NAME [-o GIF] [--json]` | Export an animated GIF preview. |

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

## Animation in v0.2

Top-level `layers` describe a shared starting pose. A named root frame uses
those layers; a child inherits another frame and changes only named layers:

```yaml
layers:
  - name: head
    operations:
      - pixel: {at: [12, 8], color: bone}
frames:
  idle_0: {}
  idle_1:
    extends: idle_0
    overrides:
      head:
        transform: {translate: [0, -1]}
animations:
  idle:
    fps: 8
    loop: true
    frames: [idle_0, idle_1, idle_0]
```

The example assumes `bone` exists in the palette. `frames` and `animations`
are optional, so existing assets still render as before. In an override,
`visible` replaces visibility, specified transform fields replace only those
fields, and `operations` replaces the entire operation list. Other fields and
layers remain inherited. Layer order does not change. Inheritance cycles,
unknown parents and unknown override targets are validation errors. See the
[exact animation format](docs/animation.md).

```sh
skullpix render examples/animated_skeleton.yaml --frame idle_0 -o build/idle_0.png
skullpix sheet examples/animated_skeleton.yaml --animation idle \
  -o build/idle.png --metadata build/idle.json
skullpix preview examples/animated_skeleton.yaml --animation idle -o build/idle.gif
```

The [animated skeleton](examples/animated_skeleton.yaml) has 6 idle, 8 walk
and 4 attack frames. Its 18 named frames reuse one set of layers and contain
only small pose changes.

```python
from skullpix import load_asset, render_frame, render_sheet, metadata_bytes, preview_bytes, save_png

asset = load_asset("examples/animated_skeleton.yaml")
image = render_frame(asset, "idle_0", strict=True)
sheet = render_sheet(asset, "idle")  # .image and .metadata
save_png(sheet.image, "build/idle.png")
open("build/idle.json", "wb").write(metadata_bytes(sheet.metadata))
open("build/idle.gif", "wb").write(preview_bytes(asset, "idle"))
```

`load_asset` validates syntax/schema and raises `AssetError` with `.result` for
structured diagnostics. `validate_asset` checks a loaded model's semantics and
returns a result. `render_asset` raises `AssetError` on errors; relaxed clipping
emits Python `UserWarning` messages. The API never invokes the CLI or reads
configuration, environment variables or network services.

## Tilesets in v0.3

Tiles reuse named frames and inheritance. Declare their order and a fixed number
of columns; IDs are zero-based list positions. Only explicitly declared seams
are checked, so caps and corners can have different outer edges:

```yaml
frames:
  floor: {}
  cracked:
    extends: floor
    overrides:
      wear:
        operations:
          - line: {from: [12, 5], to: [15, 9], color: shadow}
tilesets:
  stone:
    columns: 2
    tiles: [floor, cracked]
    seams:
      - {from: floor, to: cracked, axis: x}
```

This fragment assumes a `wear` layer and `shadow` palette entry. An `x` seam
compares right/left edges; `y` compares bottom/top edges. Mismatched RGBA pixels
are validation errors. See [exact tileset semantics and diagnostics](docs/tilesets.md).

```sh
skullpix tileset examples/stone_tiles.yaml --tileset stone \
  -o build/stone.png --metadata build/stone.json
uv run python examples/stone_room.py
```

The generic example contains ten floor, wall, cap and corner tiles. The room
script places them explicitly; it is an example consumer, not an autotile solver.

```python
from skullpix import load_asset, render_tileset, save_png, metadata_bytes

grid = render_tileset(load_asset("examples/stone_tiles.yaml"), "stone")
save_png(grid.image, "build/stone.png")
open("build/stone.json", "wb").write(metadata_bytes(grid.metadata))
```

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
  frames.py          named-frame resolution to ordinary layers
  animation.py       one-row sheets, JSON metadata, GIF previews
  tilesets.py        fixed-cell grids and tile metadata
  inspection.py      stable asset statistics
  diagnostics.py     shared error/warning contract
  png.py             canonical PNG bytes and atomic save
  cli.py             Typer command adapters
```

## Non-goals

- No GUI, painting UI or Aseprite clone.
- No vector graphics, arbitrary subpixel coordinates or arbitrary-angle rotation.
- No anti-aliased rendering or Photoshop-style filters.
- No AI image generation, image-generation model dependency or embedded LLM APIs.
- No game-engine dependency or Godot dependency.
- No proprietary formats, raster import or automatic terrain selection.
- No animation editor, interactive timeline or automatic sheet packing.

Skullpix is an independent implementation built on general raster primitives.
No implementation code was copied from Aseprite, LibreSprite or other editors.

## Limits and future direction

Each frame renders on the same canvas. YAML aliases/includes, reusable components,
variables and imported images are unsupported. Canvas dimensions are at most
4096 per axis; coordinates are within −65536…65536, box sizes within 1…65536;
source files are limited to 4 MiB and 64 nesting levels. Only JSON-compatible
YAML tags are accepted. Large flood fills and lint scans are CPU
work proportional to canvas area. This is a local tool, not a sandbox for
adversarial public uploads.

v0.3 keeps the v1 source version because all v0.1 assets retain their meaning.
Spritesheets use one horizontal row with no trimming or scaling. GIF previews
have one-bit transparency and 10 ms timing granularity; PNG sheets and JSON
metadata retain full RGBA and millisecond durations. See [future work](docs/future.md).

Later candidates include terrain/autotile rules, indexed palettes, reusable
components, deterministic noise, controlled dithering, edge highlights,
visual regression tools, optional Godot resource export, and Aseprite or
Pixelorama adapters. These remain outside the current release.

## License

[MIT](LICENSE).
