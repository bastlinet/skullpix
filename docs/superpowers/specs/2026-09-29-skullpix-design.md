# Skullpix v0.1 design

The user's detailed brief is the scope and acceptance contract: a headless,
agent-first YAML/JSON pixel-art compiler. Python 3.12+, Pillow, Pydantic,
Typer, safe YAML and pytest; MIT; no GUI, AI, imports, animation or sheets.

## Architecture

`schema.py` owns strict typed data, `parsing.py` reads safe text, `palette.py`
resolves RGBA, `operations/` changes a single Pillow RGBA image, `renderer.py`
composes layers, `validation/` produces structured diagnostics, `png.py`
provides canonical byte encoding, `cli.py` adapts these APIs to Typer.
Reusable Layer and operation models permit future frame containers without
implementing any future features now.

## Semantics

Origin is top left; x right, y down. All coordinates are integers (booleans,
floats and numeric strings rejected). Boxes are [x,y,width,height], positive
size, right/bottom exclusive. Drawing replaces exact RGBA within a layer;
layers composite source-over in declaration order. Alpha > 0 is occupied.
Flood fill matches exact RGBA, with four neighbors. Outlines add one ring
around a snapshot of occupied pixels and never overwrite occupied pixels.

Transforms apply after operations: mirror_x reverses x (left/right), mirror_y
reverses y (top/bottom), clockwise rotate 90/180/270, translate. Rotation
transposes the entire layer, swaps width/height for quarter turns, then
anchors the rotated image at (0,0) on the original output canvas. No rounding
or interpolation. Only actually occupied pixels lost by transforms trigger
clipping diagnostics. Primitive bounds are validated even for hidden layers.

Validation returns stable codes, paths, values, messages, suggestions.
Schema/syntax/color errors always prevent rendering; non-strict rendering
clips with reported diagnostics, strict rendering rejects bounds errors.
max_colors counts distinct occupied RGBA colors in the composited result and
is always an error. Lint adds optional off-palette, unused-palette, singleton
and component warnings. Warnings alone do not fail commands.

## Reproducibility

Pin Pillow raster version; commit uv.lock. Canonical PNG uses fixed RGBA8
scanlines, filter 0 and stored DEFLATE blocks, with only IHDR/IDAT/IEND.
No compression-version dependency, timestamps, metadata or random state.
Exact matrices protect primitive semantics; committed example PNG SHA-256
hashes protect complete outputs. Canonical encoding favors stable bytes over
file size. Ordinary Pillow Image.save remains available for API callers.

## Constraints and edge cases

Reject unknown fields and operations, duplicate YAML/JSON keys, YAML aliases
and non-JSON YAML tags. Limit input to 4 MiB and 64 nesting levels, dimensions to 4096 each and coordinates
and box sizes to a magnitude of 65536 to prevent accidental enormous rasters
and arithmetic overflow. No filesystem includes or implicit external inputs.
Transparent RGB is preserved within layers for exact replace/fill; final
fully transparent pixels are canonicalized to zero RGBA.

## Verification

Test parsing, every primitive, transforms (including non-square canvas),
alpha, validation and diagnostic paths, clipping from outlines/transforms,
lint, API, CLI JSON/exits, example hashes and repeated byte identity. Run the
full suite after each phase. Build/install the package and execute all four
acceptance commands. Stop at v0.1.
