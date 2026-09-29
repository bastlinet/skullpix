"""Integer raster primitives; public boxes never expose Pillow's inclusive ends."""

from PIL import Image, ImageDraw

from ..palette import RGBA
from ..schema import Operation


def line_points(start, end):
    # Canonical direction gives identical tie-breaking when endpoints are reversed.
    (x, y), (x1, y1) = sorted((start, end))
    dx, dy = abs(x1 - x), -abs(y1 - y)
    sx, sy = (1 if x < x1 else -1), (1 if y < y1 else -1)
    error = dx + dy
    while True:
        yield x, y
        if x == x1 and y == y1:
            break
        twice = 2 * error
        if twice >= dy:
            error += dy
            x += sx
        if twice <= dx:
            error += dx
            y += sy


def _put(image: Image.Image, point, color: RGBA):
    x, y = point
    if 0 <= x < image.width and 0 <= y < image.height:
        image.putpixel((x, y), color)


def bounds_points(op: Operation):
    p = op.params
    match op.kind:
        case "pixel":
            return [p.at]
        case "pixels" | "polygon":
            return p.points
        case "line":
            return [p.start, p.end]
        case "rect" | "ellipse":
            x, y, width, height = p.box
            return [(x, y), (x + width - 1, y + height - 1)]
        case "fill":
            return [p.seed]
        case _:
            return []


def out_of_bounds(op: Operation, size: tuple[int, int]) -> bool:
    width, height = size
    return any(not (0 <= x < width and 0 <= y < height) for x, y in bounds_points(op))


def draw_primitive(image: Image.Image, op: Operation, color: RGBA):
    p = op.params
    match op.kind:
        case "pixel":
            _put(image, p.at, color)
        case "pixels":
            for point in p.points:
                _put(image, point, color)
        case "line":
            for point in line_points(p.start, p.end):
                _put(image, point, color)
        case "rect" | "ellipse":
            x, y, width, height = p.box
            box = (x, y, x + width - 1, y + height - 1)
            draw = ImageDraw.Draw(image)
            # Pillow's ellipse degenerates differently at width/height 1.
            # Our public one-pixel-wide/high ellipse is exactly that line.
            method = draw.rectangle if op.kind == "rect" or min(width, height) == 1 else draw.ellipse
            method(box, fill=color if p.fill else None, outline=None if p.fill else color)
        case "polygon":
            if p.fill:
                ImageDraw.Draw(image).polygon(p.points, fill=color)
            else:
                for start, end in zip(p.points, p.points[1:] + p.points[:1]):
                    for point in line_points(start, end):
                        _put(image, point, color)
        case _:
            raise ValueError(f"Unsupported drawing primitive {op.kind}")
