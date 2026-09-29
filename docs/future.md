# Future direction (not implemented)

Keep the v0.2 proposal small: named frames, animation tags/timing, spritesheets
and JSON metadata. Reuse existing `Layer` and `Operation` models inside frames.
Specify frame ordering, per-frame dimensions, empty frames, timing, packing
order and padding before adding commands. Preserve v1 loading or introduce an
explicit new format version where semantics differ.

An illustrative future shape, deliberately rejected by the current v1 schema:

```yaml
frames:
  - name: idle-1
    layers: []
  - name: idle-2
    layers: []
animations:
  idle:
    fps: 8
    frames: [idle-1, idle-2]
```

Possible future command:

```sh
skullpix sheet frog.yaml -o frog.png --metadata frog.json
```

Longer-term paths from the same text source include sprite/animation rendering,
tilesets, metadata exports, linting, optional Godot resources and visual
regression testing. Pixel-aware operations may eventually include inner
shadows, edge highlights, controlled dithering, cluster cleanup, singleton
removal, palette reduction and indexed export. Reusable components, references,
variables, seeded noise, tileset constraints, animation tags, onion-skin
preview generation, Aseprite adapters and Pixelorama interoperability require
separate designs. None warrants a plugin framework or operation graph in v0.1.
