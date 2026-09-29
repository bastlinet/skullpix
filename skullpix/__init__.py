"""Skullpix: graphics as source code."""

__version__ = "0.2.0"

from .diagnostics import AssetError, Issue, ValidationResult
from .parsing import load_asset
from .schema import Asset
from .renderer import render_asset
from .validation import lint_asset, validate_asset
from .inspection import inspect_asset
from .png import png_bytes, save_png
from .frames import resolve_frame, render_frame
from .animation import Sheet, render_sheet, metadata_bytes, preview_bytes

__all__ = ["Asset", "AssetError", "Issue", "ValidationResult", "load_asset", "render_asset",
           "validate_asset", "lint_asset", "inspect_asset", "png_bytes", "save_png",
           "resolve_frame", "render_frame", "Sheet", "render_sheet", "metadata_bytes", "preview_bytes"]
