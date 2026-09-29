"""Exact-color operations without tolerance or dependence on traversal order."""

from collections import deque

from PIL import Image

from ..palette import RGBA

NEIGHBORS_4 = ((0, -1), (-1, 0), (1, 0), (0, 1))
NEIGHBORS_8 = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy)


def flood_fill(image: Image.Image, seed: tuple[int, int], color: RGBA):
    x, y = seed
    if not (0 <= x < image.width and 0 <= y < image.height):
        return
    pixels = image.load()
    target = pixels[x, y]
    if target == color:
        return
    queue = deque([seed])
    pixels[x, y] = color  # Mark on enqueue so each pixel is visited once.
    while queue:
        x, y = queue.popleft()
        for dx, dy in NEIGHBORS_4:
            nx, ny = x + dx, y + dy
            if 0 <= nx < image.width and 0 <= ny < image.height and pixels[nx, ny] == target:
                pixels[nx, ny] = color
                queue.append((nx, ny))


def replace_color(image: Image.Image, source: RGBA, target: RGBA):
    if source == target:
        return
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            if pixels[x, y] == source:
                pixels[x, y] = target
