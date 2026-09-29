"""Stable, machine-friendly asset statistics."""

from .diagnostics import AssetError
from .schema import Asset
from .validation.checks import _analyze, image_statistics


def inspect_asset(asset: Asset) -> dict:
    result, rendered = _analyze(asset, strict=True)
    if not result.valid:
        raise AssetError(result)
    return {"version": asset.version,
            "canvas": {"width": asset.canvas.width, "height": asset.canvas.height},
            "layers": len(asset.layers),
            "operations": sum(len(layer.operations) for layer in asset.layers),
            "palette_colors": len(asset.palette),
            **image_statistics(rendered.image)}
