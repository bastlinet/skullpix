"""Stable, machine-friendly asset statistics."""

from .diagnostics import AssetError
from .schema import Asset
from .renderer import _render
from .validation.checks import _analyze, image_statistics, validate_asset


def inspect_asset(asset: Asset) -> dict:
    if asset.frames or asset.animations:
        result = validate_asset(asset, strict=True)
        rendered = _render(asset) if result.valid else None
    else:
        result, rendered = _analyze(asset, strict=True)
    if not result.valid:
        raise AssetError(result)
    return {"version": asset.version,
            "canvas": {"width": asset.canvas.width, "height": asset.canvas.height},
            "layers": len(asset.layers),
            "operations": sum(len(layer.operations) for layer in asset.layers),
            "palette_colors": len(asset.palette),
            **image_statistics(rendered.image)}
