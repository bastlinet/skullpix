"""Fixed-cell, row-major tileset atlases built from ordinary named frames."""

from difflib import get_close_matches

from PIL import Image

from .animation import Sheet, _validate_export
from .diagnostics import AssetError, Issue, ValidationResult
from .frames import resolve_frame
from .renderer import _render
from .schema import Asset
from .validation.tilesets import dimensions, size_issue


def render_tileset(asset: Asset, name: str, *, strict: bool = True) -> Sheet:
    """Return a fresh grid atlas and stable metadata in declared tile order.

    Tile IDs are zero-based list positions. Unused cells stay transparent.
    Declared seams are correctness contracts even when clipping is relaxed.
    """
    if name not in asset.tilesets:
        raise AssetError(ValidationResult([Issue(
            "E070", "unknown-tileset", f"tilesets.{name}",
            f"No tileset named {name!r} exists.", value=name,
            suggestions=tuple(get_close_matches(name, asset.tilesets, n=3, cutoff=0.5)),
        )]))
    limit = size_issue(asset, name)
    if limit is not None:
        raise AssetError(ValidationResult([limit]))
    _validate_export(asset, strict)
    definition = asset.tilesets[name]
    width, height, rows = dimensions(asset, definition)
    tile_width, tile_height = asset.canvas.width, asset.canvas.height
    atlas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    records = []
    for index, frame_name in enumerate(definition.tiles):
        x = (index % definition.columns) * tile_width
        y = (index // definition.columns) * tile_height
        frame = _render(resolve_frame(asset, frame_name)).image
        atlas.paste(frame, (x, y))
        records.append({"id": index, "name": frame_name, "x": x, "y": y,
                        "w": tile_width, "h": tile_height})
    metadata = {"tileset": name, "tile_width": tile_width, "tile_height": tile_height,
                "columns": definition.columns, "rows": rows, "tiles": records,
                "seams": [seam.model_dump(by_alias=True) for seam in definition.seams]}
    return Sheet(atlas, metadata)
