# Tilesets in source format v1

`tilesets` is an optional mapping. Each value requires `columns` (strict integer,
1–4096) and `tiles` (non-empty ordered list of unique existing frame names).
`seams` defaults to `[]`. Names follow the existing frame naming rules.
Duplicate YAML/JSON mapping keys are rejected by the parser.

```yaml
canvas: {width: 16, height: 16}
layers: []
frames:
  floor: {}
  worn: {extends: floor}
tilesets:
  terrain:
    columns: 2
    tiles: [floor, worn]
    seams:
      - {from: floor, to: worn, axis: x}
      - {from: floor, to: floor, axis: y}
```

Tiles are ordinary named frames, using the [same inheritance and layer override
semantics](animation.md). Frames may belong to multiple tilesets or animations.
There is no second operation language, discovery, sorting or implicit tile
generation. Resolving/exporting a tile does not mutate its source or parents.

## Layout and metadata

Tile ID is its zero-based position in `tiles`. Inserting or reordering entries
changes subsequent IDs; consumers needing stable identity should use names.
For ID `i`, the rectangle is:

- `x = (i % columns) * canvas.width`
- `y = (i // columns) * canvas.height`
- `w = canvas.width`, `h = canvas.height`

Atlas rows equal `ceil(tile_count / columns)`. Atlas width includes all declared
columns, even when there are fewer tiles. Unused cells are transparent black,
including when the source canvas has an opaque background. Each occupied cell
contains the final RGBA render, including its canvas background. Partial alpha
is preserved. No trimming, packing, scaling, spacing, padding or extrusion.

```sh
skullpix tileset asset.yaml --tileset terrain -o terrain.png --metadata terrain.json
```

Default PNG output is `INPUT_STEM-TILESET.png`; metadata is optional.
`--json` returns the existing diagnostic envelope with `output`,
`metadata_output` and `tileset` (the metadata object). Invalid input leaves
existing outputs untouched. PNG and JSON files are each written atomically,
but the pair is not a transaction. Output paths cannot alias the source or each
other. CLI tileset exports enforce strict clipping.

The Python API is `render_tileset(asset, name, strict=True)`, returning the
existing `Sheet` container with `.image` (fresh Pillow RGBA image) and `.metadata`
(fresh dictionary). Encode these with `save_png`/`png_bytes` and `metadata_bytes`.
`strict=False` relaxes clipping only, never broken seam contracts.

Metadata keys are emitted in this order:

```json
{
  "tileset": "terrain",
  "tile_width": 16,
  "tile_height": 16,
  "columns": 2,
  "rows": 1,
  "tiles": [
    {"id": 0, "name": "floor", "x": 0, "y": 0, "w": 16, "h": 16},
    {"id": 1, "name": "worn", "x": 16, "y": 0, "w": 16, "h": 16}
  ],
  "seams": [
    {"from": "floor", "to": "worn", "axis": "x"},
    {"from": "floor", "to": "floor", "axis": "y"}
  ]
}
```

The actual encoder expands objects with two-space indentation, UTF-8 and one
final LF. All dimensions, IDs and positions are integers. Tile and seam arrays
retain declaration order. Identical source/compiler versions produce identical
canonical PNG and metadata bytes.

## Explicit seam contracts

Every seam requires `from`, `to` and `axis` (`x` or `y`). Both endpoints must
occur in this tileset. Self-seams are valid. An `x` seam compares the rightmost
column of `from` with the leftmost of `to`, top-to-bottom. A `y` seam compares
the bottom row of `from` with the top row of `to`, left-to-right. No reversal.

Comparison uses exact final RGBA, including alpha and canvas background.
As in ordinary rendering, fully transparent pixels have normalized black RGB.
No tolerance, fuzzy matching or automatic edge repair is applied.

`validate`, `lint`, inspection and rendering entry points check all declared
tilesets. Edge comparisons run only after structural/geometry/color validation
succeeds. Errors include a source path, mismatch count and first differing
pixel's edge offset and RGBA values. Lint's existing frame advice still applies.

These are opt-in edge equality contracts, not proof of visually pleasing joins.
Matching boundary pixels can still hide discontinuous texture or lighting.
Undeclared joins are not checked. Caps and corners may intentionally differ.
There is no terrain solver, tilemap format, engine adapter or runtime dependency.

## Diagnostics and limits

| Code | Meaning |
| --- | --- |
| E070 | Unknown tileset selected for export. |
| E071 | Missing or empty tile list. |
| E072 | Tile references an unknown frame. |
| E073 | Duplicate tile name within a tileset. |
| E074 | Missing/invalid columns. |
| E075 | Seam references a tile outside the set. |
| E076 | Declared seam pixels differ. |
| E077 | Atlas exceeds allocation limits. |
| E078 | Missing/invalid seam axis. |

Other malformed fields use the existing schema diagnostics. Atlas dimensions
are limited to 65,535 pixels per axis and 16,777,216 total pixels. Export checks
these before rendering/allocating the atlas. Seam validation retains only the
current pair of frame images, rendering pairs again as needed to bound memory.
Existing canvas/source limits still apply. No new dependency is required.
