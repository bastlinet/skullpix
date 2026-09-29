# Animation format and export semantics (Skullpix v0.2)

The `version: 1` source format remains valid. v0.2 adds two optional top-level
mappings, `frames` and `animations`. They use the existing `canvas`, `palette`,
`layers`, `constraints` and operations. All v0.1 files have the same behavior.

```yaml
version: 1
canvas: {width: 32, height: 32, background: transparent}
palette:
  transparent: "#00000000"
  bone: "#d8ccd9"
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

Frame and animation names use the palette-name syntax
`[A-Za-z_][A-Za-z0-9_-]*`. Their mappings have distinct namespaces. A frame
name can match an animation name. Duplicate keys are rejected by the YAML/JSON
parser; order of mapping keys does not determine playback order.

## Frame resolution

`frames.<name>` has optional `extends` and `overrides` fields. No other fields
are allowed. A root frame (without `extends`) starts with a deep copy of the
top-level `layers`. A child starts with a deep copy of its named parent's
**resolved** layers. Parents may appear before or after children in the file.
Cycles and missing parents fail validation. Resolution never changes its
parent, siblings or original source models.

`resolve_frame` returns an ordinary standalone asset: its resolved layers are
present, while its `frames` and `animations` mappings are empty. It can be
passed directly to `render_asset` or `validate_asset`.

`overrides` maps an **existing** layer name to a patch. This name must match
exactly one inherited layer; missing or duplicate matches are errors. A patch
may set:

| Field | Effect |
| --- | --- |
| `visible` | Replaces the inherited boolean. |
| `transform` | Replaces only the specified `translate`, `mirror_x`, `mirror_y` and/or `rotate` fields. Other transform fields remain inherited. |
| `operations` | Replaces the complete ordered operation list. `[]` clears it. |

Unmentioned fields remain inherited. Overrides never append operations, add
layers, delete layers, rename layers or change layer order. Add a shared layer
at the top level and toggle its visibility if only some frames need it. The
existing renderer receives the resolved layers as an ordinary asset. `render`
without `--frame` still draws the top-level base layers.

All declared frames, including unused ones, are validated by the rendering,
inspection and validation APIs and CLI commands. The top-level base is also
validated. A source error inside an override points to
`frames.<name>.overrides.<layer>...`. A geometric error inherited from another
frame may point to the stable virtual path
`frames.<name>.resolved.layers[index]...`.

## Animations

`animations.<name>` has a required integer `fps` from 1 to 1000, optional
strict boolean `loop` (default `true`), and a required nonempty `frames` list.
Each list element names a declared frame. Repetitions are preserved. The
renderer never guesses an order from frame names, mappings or file position.
Timing is uniform per animation; no per-frame durations or animation graph.

Metadata duration is `1000 / fps` rounded to the nearest integer millisecond,
ties upward, with a one-millisecond minimum. Thus `fps: 8` yields 125 ms and
`fps: 7` yields 143 ms. The loop flag is exported unchanged.

## Sheets and metadata

```sh
skullpix sheet examples/animated_skeleton.yaml --animation idle \
  -o build/idle.png --metadata build/idle.json
```

The sheet is transparent RGBA with one horizontal row. Every cell is exactly
the canvas width and height. There is no trimming, padding, rescaling,
anti-aliasing, bin packing or automatic discovery. Frame 0 starts at x=0,
frame 1 at x=canvas width, and so on. Each cell preserves its frame's rendered
pixels, including any configured canvas background. Repeated frame names get
separate cells. Export fails before allocation if the sheet exceeds 65,535
pixels in width or 16,777,216 pixels in area.

PNG output uses Skullpix's existing canonical encoder. Metadata is UTF-8 JSON
with the field order below, two-space indentation and one final newline.
Each record has keys in the order shown. Repeated exports are byte-identical.

```json
{
  "animation": "idle",
  "fps": 8,
  "loop": true,
  "frame_width": 32,
  "frame_height": 32,
  "frames": [
    {"name": "idle_0", "x": 0, "y": 0, "w": 32, "h": 32, "duration_ms": 125},
    {"name": "idle_1", "x": 32, "y": 0, "w": 32, "h": 32, "duration_ms": 125}
  ]
}
```

`--metadata` is optional. Without `-o`, the PNG goes to
`<input-stem>-<animation>.png` beside the source. Neither output may overwrite
the source; the metadata path must differ from the PNG path. Each output file
is written atomically after validation.
The PNG and JSON are separate writes: a metadata write failure can leave the
PNG in place. E040 identifies the path that could not be written.

## GIF preview

```sh
skullpix preview examples/animated_skeleton.yaml --animation idle -o build/idle.gif
```

The preview uses an explicitly sorted RGB palette with index zero reserved
for transparency. There is no dithering or anti-aliasing. GIF supports only
one-bit alpha: values below 128 become transparent; other pixels become fully
opaque. It supports at most 255 opaque RGB colors in one preview. Timing rounds
metadata milliseconds to the nearest 10 ms, ties upward, with a 10 ms minimum.
For example, 125 ms becomes 130 ms. A true loop adds an infinite GIF loop
extension; a false loop omits it, so the animation plays once.

Every animation entry writes a full GIF frame, including repeated or completely
transparent poses; entries are never merged.
GIF is an inspection output; use the PNG sheet plus JSON for exact RGBA and timing.
Previews render individual frames without constructing a sheet, so the sheet
width limit does not apply. A preview may contain at most 16,777,216 pixels
across all frame entries; exceeding this resource limit reports E060.

## CLI and Python

`render --frame NAME`, `sheet --animation NAME` and `preview --animation NAME`
are explicit. `validate --json` reports source and inheritance errors in the
same structured format as v0.1. `lint` checks declared frames in source order
and reports their topology separately. Palette-use advice considers all base
and override source operations, even in unused frames; each frame's color
constraint examines its final composite.

```python
from skullpix import (
    load_asset, resolve_frame, render_frame, render_sheet,
    metadata_bytes, preview_bytes, save_png,
)

asset = load_asset("examples/animated_skeleton.yaml")
resolved = resolve_frame(asset, "idle_1")  # Asset with ordinary resolved layers
image = render_frame(asset, "idle_1", strict=True)
sheet = render_sheet(asset, "idle")  # Sheet(image, metadata)
save_png(sheet.image, "build/idle.png")
json_data = metadata_bytes(sheet.metadata)
gif_data = preview_bytes(asset, "idle")
```

## New diagnostic codes

| Code | Meaning |
| --- | --- |
| E050 | Requested or inherited frame does not exist. |
| E051 | Frame inheritance cycle. |
| E052 | Override names no inherited layer. |
| E053 | Animation references an unknown frame. |
| E054 | Animation's frame list is empty or missing. |
| E055 | Invalid FPS, including zero, negative, noninteger or over 1000. |
| E056 | Override target is ambiguous because a layer name repeats. |
| E057 | Requested animation does not exist. |
| E058 | Sheet layout exceeds export limits. |
| E059 | GIF preview needs more than 255 opaque colors. |
| E060 | GIF preview exceeds the total pixel limit across all frames. |

Existing E001/E002/E011–E040 diagnostics still apply. A duplicate frame or
animation key is a parser-level E001 duplicate-key error. A wrong type or
unsupported override field is E002 at the Pydantic source path.
