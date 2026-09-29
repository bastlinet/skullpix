"""Independent rendering engine with explicit per-layer RGBA buffers."""

from dataclasses import dataclass
import warnings

from PIL import Image

from .diagnostics import AssetError, Issue
from .operations import apply_operation
from .operations.transform import transform_layer
from .palette import resolve_color
from .schema import Asset


@dataclass
class Rendered:
    image: Image.Image
    clipping: list[Issue]


def _render(asset: Asset) -> Rendered:
    size = (asset.canvas.width, asset.canvas.height)
    background = ((0, 0, 0, 0) if asset.canvas.background is None
                  else resolve_color(asset.canvas.background, asset.palette))
    final = Image.new("RGBA", size, background)
    clipping = []
    for index, layer in enumerate(asset.layers):
        image = Image.new("RGBA", size, (0, 0, 0, 0))
        for number, op in enumerate(layer.operations):
            if apply_operation(image, op, asset.palette):
                clipping.append(Issue(
                    "E020", "out-of-bounds", f"layers[{index}].operations[{number}].{op.kind}",
                    "Drawing extends outside the canvas and is clipped.",
                    value=op.params.model_dump(by_alias=True),
                ))
        image, clipped = transform_layer(image, layer.transform)
        if clipped:
            clipping.append(Issue(
                "E020", "out-of-bounds", f"layers[{index}].transform",
                "Transform moves occupied pixels outside the canvas and they are clipped.",
                value=layer.transform.model_dump(),
            ))
        if layer.visible:
            final = Image.alpha_composite(final, image)
    # Fully transparent RGB has no visual meaning in final exported assets.
    pixels = final.load()
    for y in range(final.height):
        for x in range(final.width):
            if pixels[x, y][3] == 0:
                pixels[x, y] = (0, 0, 0, 0)
    return Rendered(final, clipping)


def render_asset(asset: Asset, *, strict: bool = False) -> Image.Image:
    """Render a fresh RGBA image. Relaxed mode clips with UserWarning diagnostics.

    Strict mode rejects clipping. Invalid references and color constraints are
    always errors; call validate_asset for structured diagnostics without warnings.
    """
    from .validation.checks import _analyze, validate_asset

    if asset.frames or asset.animations or asset.tilesets:
        result = validate_asset(asset, strict=strict)
        rendered = _render(asset) if result.valid else None
    else:
        result, rendered = _analyze(asset, strict=strict)
    if not result.valid:
        raise AssetError(result)
    for issue in result.warnings:
        warnings.warn(f"{issue.code} {issue.path}: {issue.message}", UserWarning, stacklevel=2)
    return rendered.image
