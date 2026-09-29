"""Operations act on one layer; none knows about files or the CLI."""

from PIL import Image

from ..palette import resolve_color
from ..schema import Operation
from .draw import draw_primitive, out_of_bounds
from .fill import flood_fill, replace_color
from .outline import outline


def apply_operation(image: Image.Image, op: Operation, palette: dict[str, str]) -> bool:
    """Apply an operation, returning whether its requested drawing exceeds bounds."""
    p = op.params
    if op.kind == "replace_color":
        replace_color(image, resolve_color(p.source, palette), resolve_color(p.target, palette))
        return False
    color = resolve_color(p.color, palette)
    if op.kind == "fill":
        flood_fill(image, p.seed, color)
    elif op.kind == "outline":
        return outline(image, color, p.connectivity)
    else:
        draw_primitive(image, op, color)
    return out_of_bounds(op, image.size)
