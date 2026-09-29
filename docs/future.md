# Future direction after v0.3

v0.2 implements named frames, simple inheritance, uniform-FPS animations,
fixed-cell horizontal spritesheets, deterministic JSON metadata and GIF
previews. v0.3 adds fixed-cell tileset grids and explicit RGBA seam contracts. The v1 source format remains backward compatible.

Possible future work includes terrain/autotile rules, indexed palettes, reusable
components, deterministic noise, controlled dithering, edge highlights,
visual regression tools, optional Godot resource export, and Aseprite or
Pixelorama adapters. Each needs its own design and validation contract.
There is no need for a scene graph, expression language or plugin framework.
