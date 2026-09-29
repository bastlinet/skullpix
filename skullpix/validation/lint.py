"""Optional palette and topology advice, separate from correctness errors."""

from collections import deque

from PIL import Image

from ..diagnostics import Issue, ValidationResult
from ..operations.fill import NEIGHBORS_8
from ..palette import color_references, resolve_color
from ..schema import Asset
from .checks import _analyze, image_statistics


def topology(image: Image.Image) -> tuple[list[tuple[int, int]], int]:
    width, height = image.size
    alpha = image.getchannel("A").tobytes()
    unseen = bytearray(alpha)
    isolated = []
    components = 0
    for y in range(height):
        for x in range(width):
            index = y * width + x
            if alpha[index] and not any(
                0 <= x + dx < width and 0 <= y + dy < height and alpha[(y + dy) * width + x + dx]
                for dx, dy in NEIGHBORS_8
            ):
                isolated.append((x, y))
            if not unseen[index]:
                continue
            components += 1
            unseen[index] = 0
            queue = deque([(x, y)])
            while queue:
                px, py = queue.popleft()
                for dx, dy in NEIGHBORS_8:
                    nx, ny = px + dx, py + dy
                    if 0 <= nx < width and 0 <= ny < height and unseen[ny * width + nx]:
                        unseen[ny * width + nx] = 0
                        queue.append((nx, ny))
    return isolated, components


def lint_asset(asset: Asset, *, strict: bool = True, off_palette: bool = True) -> ValidationResult:
    result, rendered = _analyze(asset, strict=strict)
    if rendered is None:
        return result
    palette = {name: resolve_color(name, asset.palette) for name in asset.palette}
    declared = set(palette.values())
    used = set()
    for path, color in color_references(asset):
        rgba = resolve_color(color, asset.palette)
        used.add(rgba)
        if off_palette and color.startswith("#") and rgba not in declared:
            result.issues.append(Issue("W001", "off-palette-color", path,
                f"Direct color {color!r} is not in the declared palette.", "warning", value=color))
    for name, rgba in palette.items():
        if rgba not in used:
            result.issues.append(Issue("W002", "unused-palette-color", f"palette.{name}",
                f"Palette color {name!r} is unused by the source.", "warning", value=name))
    isolated, components = topology(rendered.image)
    if isolated:
        result.issues.append(Issue("W003", "isolated-pixel", "$",
            f"{len(isolated)} isolated pixels (no occupied 8-connected neighbor).", "warning",
            value=len(isolated), points=tuple(isolated)))
    if components > 1:
        result.issues.append(Issue("W004", "disconnected-components", "$",
            f"Sprite contains {components} disconnected 8-connected components.", "warning", value=components))
    count = image_statistics(rendered.image)["used_colors"]
    result.issues.append(Issue("I001", "palette-size", "$",
        f"Rendered sprite uses {count} occupied RGBA colors.", "info", value=count))
    return result
