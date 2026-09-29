"""Semantic checks and one render pass for geometry-dependent validation."""

from dataclasses import replace
from difflib import get_close_matches
import re

from PIL import Image

from ..diagnostics import AssetError, Issue, ValidationResult
from ..frames import resolve_frame
from ..palette import color_references, frame_color_references, resolve_color
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


_LAYER_PATH = re.compile(r"^layers\[(\d+)\](.*)$")


def _frame_issue_path(asset: Asset, frame_asset: Asset, name: str, path: str) -> str:
    match = _LAYER_PATH.match(path)
    if match is None:
        return f"frames.{name}.resolved.{path}"
    index, suffix = int(match.group(1)), match.group(2)
    layer_name = frame_asset.layers[index].name
    override = asset.frames[name].overrides.get(layer_name)
    if override is not None:
        if suffix.startswith(".transform") and override.transform is not None:
            return f"frames.{name}.overrides.{layer_name}{suffix}"
        if suffix.startswith(".operations[") and override.operations is not None:
            return f"frames.{name}.overrides.{layer_name}{suffix}"
    return f"frames.{name}.resolved.{path}"


def validate_asset(asset: Asset, *, strict: bool = True) -> ValidationResult:
    """Validate references, names, geometry and constraints of a schema-validated Asset.

    Strict mode treats clipping as an error. All other errors remain fatal in
    either mode. Parsing/schema errors are reported by load_asset via AssetError.
    """
    result = _analyze(asset, strict=strict)[0]
    if not asset.frames and not asset.animations:
        return result
    for path, color in frame_color_references(asset):
        try:
            resolve_color(color, asset.palette)
        except ValueError:
            raw = color.startswith("#")
            result.issues.append(Issue(
                "E011" if raw else "E012", "invalid-color" if raw else "unknown-palette-color", path,
                "Expected #RRGGBB or #RRGGBBAA." if raw else f"Palette has no color named {color!r}.",
                value=color,
                suggestions=() if raw else tuple(get_close_matches(color, asset.palette, n=3, cutoff=0.5)),
            ))
    for name in asset.frames:
        try:
            frame_asset = resolve_frame(asset, name)
        except AssetError as exc:
            for issue in exc.result.errors:
                if issue not in result.issues:
                    result.issues.append(issue)
            continue
        frame_result = _analyze(frame_asset, strict=strict)[0]
        for issue in frame_result.issues:
            if issue.code in ("E011", "E012"):
                continue  # Already reported once at its source location.
            result.issues.append(replace(
                issue, path=_frame_issue_path(asset, frame_asset, name, issue.path)))
    for animation_name, animation in asset.animations.items():
        for index, frame_name in enumerate(animation.frames):
            if frame_name not in asset.frames:
                result.issues.append(Issue(
                    "E053", "unknown-animation-frame",
                    f"animations.{animation_name}.frames[{index}]",
                    f"Animation references unknown frame {frame_name!r}.",
                    value=frame_name,
                    suggestions=tuple(get_close_matches(frame_name, asset.frames, n=3, cutoff=0.5)),
                ))
    return result
