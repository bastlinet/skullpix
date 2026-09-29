"""Typer adapters; engine and public API do not import this module."""

import json
from pathlib import Path
from typing import Annotated, NoReturn

import typer

from . import __version__
from .animation import metadata_bytes, preview_bytes, render_sheet
from .diagnostics import AssetError, Issue, ValidationResult
from .frames import resolve_frame
from .inspection import inspect_asset
from .parsing import load_asset
from .png import save_png, write_bytes_atomic
from .renderer import _render
from .validation import lint_asset, validate_asset
from .validation.checks import _analyze

app = typer.Typer(help="Skullpix: a deterministic, headless pixel-art compiler.",
                  no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)
Input = Annotated[Path, typer.Argument(help="YAML or JSON asset source.", metavar="INPUT")]
Json = Annotated[bool, typer.Option("--json", help="Emit stable machine-readable JSON.")]


def _json(data):
    typer.echo(json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False, allow_nan=False))


def _report(result: ValidationResult, *, json_output: bool, err: bool = False):
    if json_output:
        _json(result.to_dict())
        return
    for issue in result.issues:
        typer.echo(f"{issue.code} {issue.name}: {issue.message}", err=err)
        if issue.path != "$":
            typer.echo(f"  {issue.path} = {json.dumps(issue.value, ensure_ascii=False)}", err=err)
        if issue.suggestions:
            typer.echo("  Did you mean: " + ", ".join(issue.suggestions), err=err)
        for x, y in issue.points:
            typer.echo(f"  ({x}, {y})", err=err)
    if not result.issues:
        typer.echo("Valid", err=err)


def _fail(result: ValidationResult, json_output: bool) -> NoReturn:
    _report(result, json_output=json_output, err=not json_output)
    raise typer.Exit(1)


def _load(path: Path, json_output: bool):
    try:
        return load_asset(path)
    except AssetError as exc:
        _fail(exc.result, json_output)


@app.callback(invoke_without_command=True)
def main(version: Annotated[bool, typer.Option("--version", is_eager=True,
                                               help="Print the Skullpix version.")] = False):
    if version:
        typer.echo(__version__)
        raise typer.Exit()


@app.command()
def render(input: Input,
           output: Annotated[Path | None, typer.Option("--output", "-o", help="Output PNG path.")] = None,
           strict: Annotated[bool, typer.Option(help="Reject drawing outside the canvas.")] = False,
           frame: Annotated[str | None, typer.Option("--frame", help="Render a named frame.")] = None,
           json_output: Json = False):
    """Compile source into a canonical PNG (defaults to INPUT with .png suffix)."""
    asset = _load(input, json_output)
    if frame is None and not (asset.frames or asset.animations):
        result, rendered = _analyze(asset, strict=strict)
    else:
        try:
            frame_asset = asset if frame is None else resolve_frame(asset, frame)
        except AssetError as exc:
            _fail(exc.result, json_output)
        result = validate_asset(asset, strict=strict)
        rendered = _render(frame_asset) if result.valid else None
    if not result.valid:
        _fail(result, json_output)
    assert rendered is not None
    destination = output if output is not None else input.with_suffix(".png")
    try:
        if destination.resolve() == input.resolve():
            raise ValueError("Output must not overwrite the asset source")
        save_png(rendered.image, destination)
    except (OSError, ValueError) as exc:
        result.issues.append(Issue("E040", "output-error", "output", str(exc), value=str(destination)))
        _fail(result, json_output)
    if json_output:
        _json({**result.to_dict(), "output": str(destination)})
    else:
        if result.issues:
            _report(result, json_output=False, err=True)
        typer.echo(f"Rendered: {destination}")


@app.command()
def sheet(input: Input,
          animation: Annotated[str, typer.Option("--animation", help="Animation to export.")],
          output: Annotated[Path | None, typer.Option("--output", "-o", help="Output PNG path.")] = None,
          metadata: Annotated[Path | None, typer.Option("--metadata", help="Optional JSON metadata path.")] = None,
          json_output: Json = False):
    """Export one animation as a deterministic, one-row PNG spritesheet."""
    asset = _load(input, json_output)
    try:
        result = render_sheet(asset, animation)
    except AssetError as exc:
        _fail(exc.result, json_output)
    destination = output if output is not None else input.with_name(f"{input.stem}-{animation}.png")
    error_field, error_destination = "output", destination
    try:
        if destination.resolve() == input.resolve():
            raise ValueError("Output must not overwrite the asset source")
        if metadata is not None and metadata.resolve() in (input.resolve(), destination.resolve()):
            error_field, error_destination = "metadata", metadata
            raise ValueError("Metadata path must differ from the source and PNG output")
        save_png(result.image, destination)
        if metadata is not None:
            error_field, error_destination = "metadata", metadata
            write_bytes_atomic(metadata, metadata_bytes(result.metadata))
    except (OSError, ValueError) as exc:
        _fail(ValidationResult([Issue("E040", "output-error", error_field, str(exc),
                                      value=str(error_destination))]), json_output)
    if json_output:
        _json({**ValidationResult().to_dict(), "output": str(destination),
               "metadata_output": str(metadata) if metadata is not None else None,
               "sheet": result.metadata})
    else:
        typer.echo(f"Sheet: {destination}")
        if metadata is not None:
            typer.echo(f"Metadata: {metadata}")


@app.command()
def preview(input: Input,
            animation: Annotated[str, typer.Option("--animation", help="Animation to preview.")],
            output: Annotated[Path | None, typer.Option("--output", "-o", help="Output GIF path.")] = None,
            json_output: Json = False):
    """Export a deterministic animated GIF preview."""
    asset = _load(input, json_output)
    try:
        data = preview_bytes(asset, animation)
    except AssetError as exc:
        _fail(exc.result, json_output)
    destination = output if output is not None else input.with_name(f"{input.stem}-{animation}.gif")
    try:
        if destination.resolve() == input.resolve():
            raise ValueError("Output must not overwrite the asset source")
        write_bytes_atomic(destination, data)
    except (OSError, ValueError) as exc:
        _fail(ValidationResult([Issue("E040", "output-error", "output", str(exc),
                                      value=str(destination))]), json_output)
    if json_output:
        _json({**ValidationResult().to_dict(), "output": str(destination)})
    else:
        typer.echo(f"Preview: {destination}")


@app.command()
def validate(input: Input, json_output: Json = False):
    """Validate syntax, schema, references, bounds, transforms and constraints."""
    result = validate_asset(_load(input, json_output))
    _report(result, json_output=json_output)
    raise typer.Exit(0 if result.valid else 1)


@app.command()
def lint(input: Input, json_output: Json = False,
         strict: Annotated[bool, typer.Option("--strict/--no-strict", help="Treat clipping as an error.")] = True,
         off_palette: Annotated[bool, typer.Option("--off-palette/--no-off-palette",
                                                   help="Warn about undeclared direct colors.")] = True):
    """Validate and report palette, isolated-pixel and connected-component advice."""
    result = lint_asset(_load(input, json_output), strict=strict, off_palette=off_palette)
    _report(result, json_output=json_output)
    raise typer.Exit(0 if result.valid else 1)


@app.command()
def inspect(input: Input, json_output: Json = False):
    """Report stable source and rendered-pixel statistics."""
    asset = _load(input, json_output)
    try:
        stats = {"asset": str(input), **inspect_asset(asset)}
    except AssetError as exc:
        _fail(exc.result, json_output)
    if json_output:
        _json(stats)
    else:
        typer.echo(f"Asset: {stats['asset']}\nVersion: {stats['version']}\n"
                   f"Canvas: {stats['canvas']['width']}x{stats['canvas']['height']}\n"
                   f"Layers: {stats['layers']}\nOperations: {stats['operations']}\n"
                   f"Palette colors: {stats['palette_colors']}\nUsed colors: {stats['used_colors']}\n"
                   f"Transparent pixels: {stats['transparent_pixels']}\nOccupied pixels: {stats['occupied_pixels']}")
