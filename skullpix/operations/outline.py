"""A one-pixel outer ring computed from the layer's original occupancy."""

from PIL import Image

from ..palette import RGBA
from .fill import NEIGHBORS_4, NEIGHBORS_8


def outline(image: Image.Image, color: RGBA, connectivity: int) -> bool:
    alpha = image.getchannel("A")  # Copy: additions never become new outline seeds.
    bounds = alpha.getbbox()
    if bounds is None:
        return False
    original = alpha.load()
    pixels = image.load()
    neighbors = NEIGHBORS_4 if connectivity == 4 else NEIGHBORS_8
    clipped = False
    for y in range(bounds[1], bounds[3]):
        for x in range(bounds[0], bounds[2]):
            if original[x, y] == 0:
                continue
            for dx, dy in neighbors:
                nx, ny = x + dx, y + dy
                if not (0 <= nx < image.width and 0 <= ny < image.height):
                    clipped = True
                elif original[nx, ny] == 0:
                    pixels[nx, ny] = color
    return clipped
