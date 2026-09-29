"""Exact, case-insensitive hexadecimal RGBA conversion."""

import re
from collections.abc import Iterator, Mapping

from .schema import Asset

RGBA = tuple[int, int, int, int]
HEX_COLOR = re.compile(r"#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?\Z")


def resolve_color(color: str, palette: Mapping[str, str]) -> RGBA:
    value = palette.get(color, color)
    if not HEX_COLOR.fullmatch(value):
        raise ValueError(f"Unknown palette color or invalid hexadecimal color {color!r}")
    if len(value) == 7:
        value += "ff"
    return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5, 7))


def color_references(asset: Asset) -> Iterator[tuple[str, str]]:
    if asset.canvas.background is not None:
        yield "canvas.background", asset.canvas.background
    for index, layer in enumerate(asset.layers):
        for number, op in enumerate(layer.operations):
            prefix = f"layers[{index}].operations[{number}].{op.kind}"
            params = op.params.model_dump(by_alias=True)
            for field in ("color", "from", "to"):
                if isinstance(params.get(field), str):
                    yield f"{prefix}.{field}", params[field]
