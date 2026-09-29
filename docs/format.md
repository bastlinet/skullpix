# Skullpix format v1

YAML is canonical; `.json` accepts the same data model. `.yml` also works.
UTF-8 is required. Quote hexadecimal colors (`#` starts a YAML comment).
PyYAML uses YAML 1.1 scalar rules; quote symbolic names such as `on`, `off`,
`yes` or `no` if used as keys/values. Duplicate keys, aliases, merge keys and
unsafe tags are rejected. There are no includes or external inputs.

Unknown fields fail schema validation. The input root is one mapping.

| Field | Requirement/default |
| --- | --- |
| `version` | Integer `1`; omitted means `1` in v0.1. |
| `canvas.width`, `canvas.height` | Required integers, 1…4096. |
| `canvas.background` | Palette name or hexadecimal RGBA; omitted/null means transparent black. |
| `palette` | Mapping of symbolic names to quoted `#RRGGBB`/`#RRGGBBAA`; default `{}`. |
| `layers` | Ordered list; default `[]`. |
| `constraints.max_colors` | Optional positive integer; distinct occupied colors in final image. |

Palette names match `[A-Za-z_][A-Za-z0-9_-]*`, at most 128 characters. Hexadecimal
digits are case-insensitive; names are case-sensitive. Six-digit colors imply
alpha 255. Eight-digit colors put alpha last: `#ff000080` is half-opacity red.

## Coordinates and boxes

`(0, 0)` is the top-left pixel; x increases right and y increases down.
Coordinates are integers within −65536…65536. No floats, booleans, numeric
strings, subpixels or silent rounding. Negative coordinates are representable
so lint can explain clipping and translations can move left/up.

All boxes are **`[x, y, width, height]`**, with positive integer dimensions
1…65536. They cover x through x+width−1 and y through y+height−1. A size of
one is a pixel, not an empty box. `fill` is a strict boolean, default `true`.
Unfilled primitives have a one-pixel border.

## Layers and alpha

```yaml
layers:
  - name: body
    visible: true
    transform:
      mirror_x: false
      mirror_y: false
      rotate: 0
      translate: [0, 0]
    operations: []
```

Names must be nonempty, unique strings (at most 128 characters). Each layer
starts as a canvas-sized transparent RGBA image. Operations execute in list
order and **replace RGBA**, including transparent writes that erase earlier
pixels in the same layer. They never read earlier layers or the background.
Color replacement and flood fill compare all four channels exactly.

After operations and transforms, visible layers composite source-over in
declaration order onto the background. Later layers appear on top. Transparent
writes on a later layer reveal the earlier layer; they cannot erase it. Alpha
blending between layers can create colors outside the declared palette.

All nonzero alpha counts as occupied for outlines, bounds of transforms,
components, isolated pixels, statistics and color limits. Fully transparent
pixels are excluded from used-color counts. Their RGB is preserved during
operations but normalized to `(0,0,0,0)` in the final image. Hidden layers do
not contribute to image statistics, but all their data and clipping is validated.

## Operations

Each operation is a mapping containing exactly one supported key.

```yaml
operations:
  - pixel:
      at: [10, 12]
      color: bone
  - pixels:
      color: bone
      points: [[10, 12], [11, 12], [12, 12]]
  - line:
      from: [4, 8]
      to: [20, 8]
      color: outline
  - rect:
      box: [4, 6, 12, 8]
      color: bone
      fill: true
  - ellipse:
      box: [6, 4, 20, 16]
      color: bone
      fill: true
  - polygon:
      points: [[8, 4], [20, 4], [24, 16], [5, 16]]
      color: bone
      fill: false
  - fill:
      seed: [12, 12]
      color: bone
  - replace_color:
      from: bone
      to: bone_dark
  - outline:
      color: outline
      connectivity: 8
```

The snippets assume referenced colors exist in the asset palette.

- `pixel` writes one coordinate. `pixels` requires at least one point; repeated
  coordinates are harmless exact writes.
- `line` uses integer Bresenham and includes both endpoints. Endpoints are
  sorted lexicographically before rasterization so reversing them gives the
  same pixels. Ties advance an axis when `2*error >= dy` / `<= dx` in the
  symmetric Bresenham algorithm.
- `rect` and `ellipse` adapt public dimensions to Pillow's inclusive bounding
  coordinates internally. One-pixel-wide/high ellipses are lines. Ellipse
  edge pixels follow the pinned Pillow raster implementation, without AA.
- `polygon` needs at least three points and closes automatically. Filled
  polygons use Pillow's pinned integer rasterizer (including its handling of
  self-intersections); borders use the same Bresenham lines as `line`.
- `fill` replaces the seed's exact RGBA region using **4-connectivity** (up,
  left, right, down). Diagonal contact does not connect regions. If the seed
  is outside the canvas, the operation does nothing and reports clipping.
- `replace_color` affects all matching pixels of the current layer, including
  transparent pixels if the source matches them. It never affects other layers.
- `outline` takes a snapshot of all occupied pixels and adds **one ring** at
  adjacent transparent pixels. Connectivity 4 uses cardinal neighbors; 8
  also includes diagonals and is the default. It does not overwrite occupied
  pixels or recursively outline its own additions. It also outlines edges
  inside holes. A second outline operation sees the first outline's result.

Pillow behavior is documented in its [ImageDraw reference](https://pillow.readthedocs.io/en/stable/reference/ImageDraw.html);
Skullpix's exact matrices and pinned dependency establish the v0.1 raster contract.

## Transforms

Layer transforms operate after all operations, on the **whole canvas-sized
layer**, not the occupied bounding box. Order is fixed regardless of YAML key order:

1. `mirror_x: true` reverses x: `(x,y) → (W−1−x,y)`, a left/right flip about
   the vertical centerline.
2. `mirror_y: true` reverses y: `(x,y) → (x,H−1−y)`, a top/bottom flip about
   the horizontal centerline.
3. `rotate` is **clockwise**: 0 (identity/default), 90, 180 or 270 only.
4. `translate: [dx,dy]` adds the integer offset.

For the rotation step, coordinate mappings and intermediate dimensions are:

| Degrees | Coordinate | Dimensions |
| --- | --- | --- |
| 90 | `(H−1−y, x)` | H × W |
| 180 | `(W−1−x, H−1−y)` | W × H |
| 270 | `(y, W−1−x)` | H × W |

The intermediate image is translated then placed with its top-left at `(0,0)`
on the original W×H canvas. There is no center rounding or interpolation.
On rectangular canvases, quarter turns can lose pixels; translation can bring
them back before final clipping. Lost occupied pixels report a bounds issue.
Operations themselves clip before transforms, so transforms cannot recover
pixels that an earlier operation already drew outside the original canvas.

## Validation and lint

Primitive coordinate bounds, boxes and polygon vertices are checked even if
their clipped parts would be transparent. Outline growth and transforms are
checked using actual intermediate pixels. Diagnostics are ordered by source
traversal; isolated pixel coordinates are ordered by y then x.

| Code | Name | Meaning |
| --- | --- | --- |
| E000 | input-error | Cannot read source. |
| E001 | syntax-error | Invalid encoding/YAML/JSON, duplicate key, alias, unsupported extension or file-size limit. |
| E002 | schema-error | Missing/extra field, invalid scalar type, dimension, coordinate, color declaration or transform. |
| E011 | invalid-color | Direct color is not #RRGGBB/#RRGGBBAA. |
| E012 | unknown-palette-color | Unknown symbolic reference; includes close-name suggestions. |
| E013 | duplicate-layer-name | A layer name is already used. |
| E014 | unsupported-operation | Unknown operation or not exactly one operation key. |
| E020 / W020 | out-of-bounds | Error in strict validation; warning with relaxed clipping. |
| E030 | max-colors | Final occupied RGBA color count exceeds constraint. |
| E040 | output-error | Cannot write PNG or output would overwrite source. |
| W001 | off-palette-color | A direct color is absent from palette values. Optional lint rule. |
| W002 | unused-palette-color | No source color reference resolves to this palette RGBA value. |
| W003 | isolated-pixel | Occupied pixel has no occupied 8-connected neighbor. |
| W004 | disconnected-components | More than one occupied 8-connected component. |
| I001 | palette-size | Count of distinct occupied colors after composition. |

Off-palette and unused checks compare resolved RGBA values, so a raw hex
matching a named color counts as palette usage. Hidden and overwritten source
operations still count as references for unused-color lint. Color-count
constraints and topology instead inspect the final visible composite.
Singletons and disconnected components may be intentional and never fail a build.
There is no anti-alias detector or raster import in v0.1.

`ValidationResult.to_dict()` returns `valid`, `errors`, `warnings`, and `info`.
Every diagnostic has `code`, `name`, `severity`, `path`, `message`, `value`,
`suggestions` and `points`. Empty lists and null values are explicit. Paths
use source field names with zero-based list indexes; `$` is the document root.
Non-JSON YAML values in schema diagnostics are represented as strings.

Successful `inspect --json` returns `asset`, `version`, `canvas`, `layers`,
`operations`, `palette_colors`, `used_colors`, `transparent_pixels`, and
`occupied_pixels`. Layer/operation counts include hidden source layers;
pixel/color counts describe the final image. Invalid input returns the usual
validation object and exits 1 instead.
