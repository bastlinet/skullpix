"""Safe YAML/JSON loading with duplicate-key and alias rejection."""

import json
import math
from pathlib import Path

import yaml
from pydantic import ValidationError

from .diagnostics import AssetError, Issue, ValidationResult
from .schema import Asset

MAX_INPUT_BYTES = 4 * 1024 * 1024


class _Loader(yaml.SafeLoader):
    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            event = self.peek_event()
            raise yaml.constructor.ConstructorError(
                None, None, "YAML aliases are not supported; use explicit values", event.start_mark)
        return super().compose_node(parent, index)

    def construct_mapping(self, node, deep=False):
        mapping = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            if not isinstance(key, str):
                raise yaml.constructor.ConstructorError(
                    None, None, "Mapping keys must be strings", key_node.start_mark)
            if key in mapping:
                raise yaml.constructor.ConstructorError(
                    None, None, f"Duplicate key {key!r}", key_node.start_mark)
            mapping[key] = self.construct_object(value_node, deep=deep)
        return mapping


def _json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate key {key!r}")
        result[key] = value
    return result


def _invalid_constant(value):
    raise ValueError(f"Invalid JSON constant {value}")


def _path(location) -> str:
    result = ""
    for part in location:
        if isinstance(part, int):
            result += f"[{part}]"
        elif not str(part).startswith("$"):
            result += ("." if result else "") + str(part)
    return result or "$"


def _json_value(value):
    # YAML may construct dates, bytes or sets. Keep diagnostics JSON-safe.
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def load_asset(path: str | Path) -> Asset:
    path = Path(path)
    try:
        with path.open("rb") as stream:
            raw = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise AssetError(ValidationResult([Issue("E000", "input-error", "$", str(exc))])) from exc
    try:
        if len(raw) > MAX_INPUT_BYTES:
            raise ValueError("Asset exceeds the 4 MiB input limit")
        source = raw.decode("utf-8")
        if path.suffix.lower() == ".json":
            data = json.loads(source, object_pairs_hook=_json_object, parse_constant=_invalid_constant)
        elif path.suffix.lower() in (".yaml", ".yml"):
            data = yaml.load(source, Loader=_Loader)
        else:
            raise ValueError("Expected a .yaml, .yml or .json input file")
    except (ValueError, yaml.YAMLError, RecursionError) as exc:
        raise AssetError(ValidationResult([Issue("E001", "syntax-error", "$", str(exc))])) from exc
    try:
        return Asset.model_validate(data)
    except ValidationError as exc:
        issues = []
        for error in exc.errors(include_url=False):
            operation_error = error["type"] in ("union_tag_invalid", "union_tag_not_found")
            issues.append(Issue(
                "E014" if operation_error else "E002",
                "unsupported-operation" if operation_error else "schema-error",
                _path(error["loc"]),
                "Expected exactly one supported operation key: pixel, pixels, line, rect, ellipse, "
                "polygon, fill, replace_color, outline" if operation_error else error["msg"],
                value=_json_value(error.get("input")),
            ))
        raise AssetError(ValidationResult(issues)) from exc
