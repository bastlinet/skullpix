"""Resolve a named frame to ordinary v0.1 layers without mutating its source."""

from difflib import get_close_matches
import warnings

from .diagnostics import AssetError, Issue, ValidationResult
from .schema import Asset, Layer, LayerOverride, Transform


def _error(code: str, name: str, path: str, message: str, value=None, suggestions=()):
    raise AssetError(ValidationResult([Issue(code, name, path, message,
                                              value=value, suggestions=tuple(suggestions))]))


def _override_layer(layer: Layer, override: LayerOverride) -> Layer:
    changes = {}
    if override.visible is not None:
        changes["visible"] = override.visible
    if override.operations is not None:
        changes["operations"] = override.operations
    if override.transform is not None:
        fields = layer.transform.model_dump()
        fields.update(override.transform.model_dump(exclude_none=True))
        changes["transform"] = Transform.model_validate(fields)
    return layer.model_copy(update=changes, deep=True)


def resolve_frame(asset: Asset, name: str) -> Asset:
    """Return a fresh Asset whose layers are the resolved frame's layers.

    Roots inherit top-level ``layers``. Descendants inherit their named parent.
    Overrides match existing layer names and preserve layer order.
    """
    if name not in asset.frames:
        _error("E050", "unknown-frame", f"frames.{name}",
               f"No frame named {name!r} exists.", name,
               get_close_matches(name, asset.frames, n=3, cutoff=0.5))
    chain: list[str] = []
    seen: dict[str, int] = {}
    current = name
    while True:
        seen[current] = len(chain)
        chain.append(current)
        parent = asset.frames[current].extends
        if parent is None:
            break
        if parent not in asset.frames:
            _error("E050", "unknown-parent-frame", f"frames.{current}.extends",
                   f"Parent frame {parent!r} does not exist.", parent,
                   get_close_matches(parent, asset.frames, n=3, cutoff=0.5))
        if parent in seen:
            cycle = " -> ".join((*chain[seen[parent]:], parent))
            _error("E051", "frame-inheritance-cycle", f"frames.{current}.extends",
                   f"Frame inheritance cycle: {cycle}.", parent)
        current = parent

    layers = [layer.model_copy(deep=True) for layer in asset.layers]
    for current in reversed(chain):
        frame = asset.frames[current]
        names = [layer.name for layer in layers]
        for target, override in frame.overrides.items():
            path = f"frames.{current}.overrides.{target}"
            count = names.count(target)
            if count == 0:
                _error("E052", "unknown-override-target", path,
                       f"No layer named {target!r} exists in this frame.", target,
                       get_close_matches(target, names, n=3, cutoff=0.5))
            if count > 1:
                _error("E056", "ambiguous-override-target", path,
                       f"Layer name {target!r} occurs {count} times.", target)
            index = names.index(target)
            layers[index] = _override_layer(layers[index], override)
    # Pydantic inserts update values by reference even with deep=True. Copy
    # after replacement so override operations are isolated, and the original
    # frame graph is not needlessly copied just to be discarded.
    return asset.model_copy(update={
        "layers": layers, "frames": {}, "animations": {}, "tilesets": {},
    }).model_copy(deep=True)


def render_frame(asset: Asset, name: str, *, strict: bool = False):
    """Render one named frame through the existing single-canvas renderer."""
    from .renderer import _render
    from .validation.checks import validate_asset

    resolved = resolve_frame(asset, name)
    result = validate_asset(asset, strict=strict)
    if not result.valid:
        raise AssetError(result)
    for issue in result.warnings:
        warnings.warn(f"{issue.code} {issue.path}: {issue.message}", UserWarning, stacklevel=2)
    return _render(resolved).image
