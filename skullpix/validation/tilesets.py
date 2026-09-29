"""Explicit tileset references, allocation limits and edge contracts."""

from difflib import get_close_matches

from ..diagnostics import Issue
from ..frames import resolve_frame
from ..renderer import _render
from ..schema import Asset, Tileset

MAX_TILESET_PIXELS = 16_777_216
MAX_TILESET_DIMENSION = 65_535


def dimensions(asset: Asset, tileset: Tileset) -> tuple[int, int, int]:
    rows = (len(tileset.tiles) + tileset.columns - 1) // tileset.columns
    return (tileset.columns * asset.canvas.width, rows * asset.canvas.height, rows)


def size_issue(asset: Asset, name: str) -> Issue | None:
    width, height, _ = dimensions(asset, asset.tilesets[name])
    if (max(width, height) > MAX_TILESET_DIMENSION
            or width * height > MAX_TILESET_PIXELS):
        return Issue(
            "E077", "tileset-too-large", f"tilesets.{name}",
            "The grid exceeds the 65,535-pixel dimension or 16,777,216-pixel area limit.",
            value={"width": width, "height": height},
        )
    return None


def reference_issues(asset: Asset) -> list[Issue]:
    issues = []
    for name, tileset in asset.tilesets.items():
        path = f"tilesets.{name}"
        limit = size_issue(asset, name)
        if limit is not None:
            issues.append(limit)
        seen = set()
        for index, tile in enumerate(tileset.tiles):
            if tile not in asset.frames:
                issues.append(Issue(
                    "E072", "unknown-tile-frame", f"{path}.tiles[{index}]",
                    f"Tile references unknown frame {tile!r}.", value=tile,
                    suggestions=tuple(get_close_matches(tile, asset.frames, n=3, cutoff=0.5)),
                ))
            if tile in seen:
                issues.append(Issue(
                    "E073", "duplicate-tile", f"{path}.tiles[{index}]",
                    f"Tile {tile!r} already appears in this tileset; tile names must be unique.",
                    value=tile,
                ))
            seen.add(tile)
        for index, seam in enumerate(tileset.seams):
            for field, tile in (("from", seam.source), ("to", seam.target)):
                if tile not in seen:
                    issues.append(Issue(
                        "E075", "unknown-seam-tile", f"{path}.seams[{index}].{field}",
                        f"Seam references tile {tile!r} outside this tileset.", value=tile,
                        suggestions=tuple(get_close_matches(tile, tileset.tiles, n=3, cutoff=0.5)),
                    ))
    return issues


def seam_issues(asset: Asset) -> list[Issue]:
    """Compare declared edges after references and frame geometry are valid.

    Keep only the current pair of images, not every resolved tile in memory.
    Both edges run in canvas order: top-to-bottom or left-to-right.
    """
    issues = []
    width, height = asset.canvas.width, asset.canvas.height
    for name, tileset in asset.tilesets.items():
        for index, seam in enumerate(tileset.seams):
            source = _render(resolve_frame(asset, seam.source)).image
            target = (source if seam.source == seam.target
                      else _render(resolve_frame(asset, seam.target)).image)
            if seam.axis == "x":
                edge_a = source.crop((width - 1, 0, width, height))
                edge_b = target.crop((0, 0, 1, height))
            else:
                edge_a = source.crop((0, height - 1, width, height))
                edge_b = target.crop((0, 0, width, 1))
            count, first = 0, None
            for offset, (a, b) in enumerate(zip(edge_a.get_flattened_data(), edge_b.get_flattened_data())):
                if a != b:
                    count += 1
                    if first is None:
                        first = {"offset": offset, "from": list(a), "to": list(b)}
            if count:
                issues.append(Issue(
                    "E076", "seam-mismatch", f"tilesets.{name}.seams[{index}]",
                    f"{count} RGBA pixels differ along the {seam.axis} seam "
                    f"from {seam.source!r} to {seam.target!r}.",
                    value={"from": seam.source, "to": seam.target, "axis": seam.axis,
                           "mismatched_pixels": count, "edge_pixels": height if seam.axis == "x" else width,
                           "first_mismatch": first},
                ))
    return issues
