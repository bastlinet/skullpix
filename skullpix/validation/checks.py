"""Semantic checks and one render pass for geometry-dependent validation."""

from dataclasses import replace
from difflib import get_close_matches

from PIL import Image

from ..diagnostics import Issue, ValidationResult
from ..palette import color_references, resolve_color
from ..renderer import Rendered, _render
from ..schema import Asset


def image_statistics(image: Image.Image) -> dict[str, int]:
    colors = image.getcolors(image.width * image.height)
    transparent = sum(count for count, rgba in colors if rgba[3] == 0)
    return {"used_colors": sum(1 for _, rgba in colors if rgba[3] > 0),
            "transparent_pixels": transparent,
            "occupied_pixels": image.width * image.height - transparent}


def _analyze(asset: Asset, *, strict: bool) -> tuple[ValidationResult, Rendered | None]:
    issues = []
    for path, color in color_references(asset):
        try:
            resolve_color(color, asset.palette)
        except ValueError:
            raw = color.startswith("#")
            issues.append(Issue(
                "E011" if raw else "E012", "invalid-color" if raw else "unknown-palette-color", path,
                "Expected #RRGGBB or #RRGGBBAA." if raw else f"Palette has no color named {color!r}.",
                value=color,
                suggestions=() if raw else tuple(get_close_matches(color, asset.palette, n=3, cutoff=0.5)),
            ))
    seen = set()
    for index, layer in enumerate(asset.layers):
        if layer.name in seen:
            issues.append(Issue("E013", "duplicate-layer-name", f"layers[{index}].name",
                                f"Layer name {layer.name!r} is already in use.", value=layer.name))
        seen.add(layer.name)
    if issues:
        return ValidationResult(issues), None
    rendered = _render(asset)
    issues.extend(rendered.clipping if strict else [
        replace(i, code="W020", severity="warning") for i in rendered.clipping])
    maximum = asset.constraints.max_colors
    if maximum is not None:
        count = image_statistics(rendered.image)["used_colors"]
        if count > maximum:
            issues.append(Issue("E030", "max-colors", "constraints.max_colors",
                                f"Rendered sprite uses {count} occupied RGBA colors; maximum is {maximum}.",
                                value=count))
    return ValidationResult(issues), rendered


def validate_asset(asset: Asset, *, strict: bool = True) -> ValidationResult:
    """Validate references, names, geometry and constraints of a schema-validated Asset.

    Strict mode treats clipping as an error. All other errors remain fatal in
    either mode. Parsing/schema errors are reported by load_asset via AssetError.
    """
    return _analyze(asset, strict=strict)[0]
