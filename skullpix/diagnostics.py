"""Stable diagnostics shared by parsing, validation and CLI clients."""

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


@dataclass(frozen=True)
class Issue:
    code: str
    name: str
    path: str
    message: str
    severity: Literal["error", "warning", "info"] = "error"
    value: Any = None
    suggestions: tuple[str, ...] = ()
    points: tuple[tuple[int, int], ...] = ()

    def to_dict(self) -> dict:
        data = asdict(self)
        data["suggestions"] = list(self.suggestions)
        data["points"] = [list(point) for point in self.points]
        return data


@dataclass
class ValidationResult:
    issues: list[Issue] = field(default_factory=list)

    @property
    def errors(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "error"]

    @property
    def warnings(self) -> list[Issue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    @property
    def valid(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict:
        return {"valid": self.valid, "errors": [i.to_dict() for i in self.errors],
                "warnings": [i.to_dict() for i in self.warnings],
                "info": [i.to_dict() for i in self.issues if i.severity == "info"]}


class AssetError(ValueError):
    def __init__(self, result: ValidationResult):
        self.result = result
        super().__init__("\n".join(f"{i.code} {i.path}: {i.message}" for i in result.errors))
