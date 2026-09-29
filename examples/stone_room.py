"""Assemble an explicit demonstration map from tileset metadata, not autotiling.

Run: uv run python examples/stone_room.py
"""
from pathlib import Path

from PIL import Image

from skullpix import load_asset, render_tileset, save_png

# Names are deliberately explicit. The compiler does not infer terrain or corners.
ROOM = [
    ["corner_left", *["floor"] * 10, "corner_right"],
    ["wall_left", *[None] * 10, "wall_right"],
    ["wall_left", None, None, "floor_left", "floor_cracked", "floor_right", *[None] * 5, "wall_right"],
    ["wall_left", *[None] * 10, "wall_right"],
    ["wall_left", *[None] * 6, "floor_left", "floor", "floor_right", None, "wall_right"],
    ["wall_left", *[None] * 10, "wall_right"],
    ["corner_left", "floor", "floor_cracked", "floor", "floor", "floor_cracked",
     "floor", "floor", "floor_cracked", "floor", "floor", "corner_right"],
    ["wall_left", "wall", "wall_cracked", "wall", "wall", "wall_cracked",
     "wall", "wall", "wall_cracked", "wall", "wall", "wall_right"],
]


def main():
    source = Path(__file__).with_name("stone_tiles.yaml")
    sheet = render_tileset(load_asset(source), "stone")
    records = {tile["name"]: tile for tile in sheet.metadata["tiles"]}
    width, height = sheet.metadata["tile_width"], sheet.metadata["tile_height"]
    room = Image.new("RGBA", (len(ROOM[0]) * width, len(ROOM) * height))
    for row, tiles in enumerate(ROOM):
        assert len(tiles) == len(ROOM[0])
        for column, name in enumerate(tiles):
            if name is not None:
                tile = records[name]
                image = sheet.image.crop((tile["x"], tile["y"], tile["x"] + width, tile["y"] + height))
                room.paste(image, (column * width, row * height))
    output = Path("build/tilesets/stone-room.png")
    save_png(room, output)
    print(output)


if __name__ == "__main__":
    main()
