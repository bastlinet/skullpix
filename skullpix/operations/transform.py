"""Exact whole-layer flips, clockwise quarter turns, then translation."""

from PIL import Image

from ..schema import Transform


def transform_layer(image: Image.Image, transform: Transform) -> tuple[Image.Image, bool]:
    size = image.size
    if transform.mirror_x:
        image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if transform.mirror_y:
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    rotations = {90: Image.Transpose.ROTATE_270, 180: Image.Transpose.ROTATE_180,
                 270: Image.Transpose.ROTATE_90}
    if transform.rotate:
        image = image.transpose(rotations[transform.rotate])
    dx, dy = transform.translate
    bounds = image.getchannel("A").getbbox()
    clipped = bounds is not None and (
        bounds[0] + dx < 0 or bounds[1] + dy < 0
        or bounds[2] + dx > size[0] or bounds[3] + dy > size[1]
    )
    if image.size == size and dx == dy == 0:
        return image, False
    result = Image.new("RGBA", size, (0, 0, 0, 0))
    result.paste(image, (dx, dy))  # No mask: preserve exact RGBA, including alpha.
    return result, clipped
