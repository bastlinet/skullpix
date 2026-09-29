"""One-row spritesheets, deterministic metadata and indexed GIF previews."""

from dataclasses import dataclass
from difflib import get_close_matches
from io import BytesIO
import json

from PIL import GifImagePlugin, Image

from .diagnostics import AssetError, Issue, ValidationResult
from .frames import render_frame
from .schema import Asset, Animation
from .validation.checks import validate_asset

MAX_SHEET_PIXELS = 16_777_216
MAX_SHEET_WIDTH = 65_535


@dataclass(frozen=True)
class Sheet:
    image: Image.Image
    metadata: dict


def _animation(asset: Asset, name: str) -> Animation:
    if name not in asset.animations:
        raise AssetError(ValidationResult([Issue(
            "E057", "unknown-animation", f"animations.{name}",
            f"No animation named {name!r} exists.", value=name,
            suggestions=tuple(get_close_matches(name, asset.animations, n=3, cutoff=0.5)),
        )]))
    return asset.animations[name]


def _duration_ms(fps: int) -> int:
    # Round to nearest integer millisecond, ties upward; never return zero.
    return max(1, (1000 + fps // 2) // fps)


def render_sheet(asset: Asset, animation: str, *, strict: bool = True) -> Sheet:
    """Render an animation's explicit frame list into fixed cells in one row."""
    definition = _animation(asset, animation)
    result = validate_asset(asset, strict=strict)
    if not result.valid:
        raise AssetError(result)
    width, height = asset.canvas.width, asset.canvas.height
    sheet_width = width * len(definition.frames)
    if sheet_width > MAX_SHEET_WIDTH or sheet_width * height > MAX_SHEET_PIXELS:
        raise AssetError(ValidationResult([Issue(
            "E058", "sheet-too-large", f"animations.{animation}.frames",
            "The one-row spritesheet exceeds the 65,535-pixel width or 16,777,216-pixel area limit.",
            value={"width": sheet_width, "height": height},
        )]))
    image = Image.new("RGBA", (sheet_width, height), (0, 0, 0, 0))
    records = []
    duration = _duration_ms(definition.fps)
    for index, frame_name in enumerate(definition.frames):
        frame = render_frame(asset, frame_name, strict=strict)
        x = index * width
        image.paste(frame, (x, 0))
        records.append({"name": frame_name, "x": x, "y": 0, "w": width, "h": height,
                        "duration_ms": duration})
    metadata = {"animation": animation, "fps": definition.fps, "loop": definition.loop,
                "frame_width": width, "frame_height": height, "frames": records}
    return Sheet(image, metadata)


def metadata_bytes(metadata: dict) -> bytes:
    """UTF-8 JSON, insertion-ordered keys, two-space indent and final newline."""
    return (json.dumps(metadata, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def preview_bytes(asset: Asset, animation: str, *, strict: bool = True) -> bytes:
    """Render a repeatable GIF with a single sorted RGB palette and no dithering.

    GIF has one-bit alpha and 10 ms timing ticks. Alpha below 128 becomes
    transparent; other pixels become opaque. Durations round to the nearest
    10 ms. A preview with over 255 opaque RGB colors is rejected explicitly.
    """
    sheet = render_sheet(asset, animation, strict=strict)
    width, height = asset.canvas.width, asset.canvas.height
    rgba_frames = [sheet.image.crop((i * width, 0, (i + 1) * width, height))
                   for i in range(len(sheet.metadata["frames"]))]
    colors = sorted({pixel[:3] for frame in rgba_frames
                     for pixel in frame.get_flattened_data() if pixel[3] >= 128})
    if len(colors) > 255:
        raise AssetError(ValidationResult([Issue(
            "E059", "preview-too-many-colors", f"animations.{animation}",
            "GIF preview supports at most 255 opaque RGB colors.", value=len(colors),
        )]))
    color_to_index = {rgb: index + 1 for index, rgb in enumerate(colors)}
    palette = [channel for rgb in ((0, 0, 0), *colors) for channel in rgb]
    palette.extend([0] * (768 - len(palette)))
    frames = []
    for frame in rgba_frames:
        indexes = bytes(0 if pixel[3] < 128 else color_to_index[pixel[:3]]
                        for pixel in frame.get_flattened_data())
        indexed = Image.frombytes("P", frame.size, indexes)
        indexed.putpalette(palette)
        indexed.info["transparency"] = 0
        frames.append(indexed)
    duration = sheet.metadata["frames"][0]["duration_ms"]
    gif_duration = max(10, ((duration + 5) // 10) * 10)
    options = {"transparency": 0, "background": 0, "optimize": False}
    if sheet.metadata["loop"]:
        options["loop"] = 0
    output = BytesIO()
    # Pillow's save_all path delta-optimizes frames. A wholly transparent
    # frame can then emit a second global header, and identical frames merge
    # into a duration that may overflow GIF's 16-bit centisecond field.
    # Write one global header and one full image record per source frame.
    header, _ = GifImagePlugin.getheader(frames[0].copy(), info=options)
    output.writelines(header)
    for frame in frames:
        output.writelines(GifImagePlugin.getdata(
            frame.copy(), duration=gif_duration, disposal=2, transparency=0))
    output.write(b";")
    return output.getvalue()
