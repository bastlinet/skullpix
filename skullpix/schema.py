"""Version 1 authoring models; no rendering or CLI dependencies."""

from typing import Annotated, Literal

from pydantic import (
    BaseModel, BeforeValidator, ConfigDict, Discriminator, Field,
    RootModel, StrictBool, StrictInt, Tag,
)

Coordinate = Annotated[StrictInt, Field(ge=-65536, le=65536)]
Extent = Annotated[StrictInt, Field(gt=0, le=65536)]
Dimension = Annotated[StrictInt, Field(gt=0, le=4096)]
Point = tuple[Coordinate, Coordinate]
Box = tuple[Coordinate, Coordinate, Extent, Extent]
Name = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_-]*$", max_length=128)]
HexColor = Annotated[str, Field(pattern=r"^#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?$")]
Color = Annotated[str, Field(min_length=1, max_length=128)]


def _integer(value):
    if type(value) is not int:
        raise ValueError("Expected an integer, without coercion")
    return value


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Canvas(Model):
    width: Dimension
    height: Dimension
    background: Color | None = None


class Pixel(Model):
    at: Point
    color: Color


class Pixels(Model):
    points: Annotated[list[Point], Field(min_length=1)]
    color: Color


class Line(Model):
    start: Point = Field(alias="from")
    end: Point = Field(alias="to")
    color: Color


class Rect(Model):
    box: Box
    color: Color
    fill: StrictBool = True


class Ellipse(Rect):
    pass


class Polygon(Model):
    points: Annotated[list[Point], Field(min_length=3)]
    color: Color
    fill: StrictBool = True


class Fill(Model):
    seed: Point
    color: Color


class ReplaceColor(Model):
    source: Color = Field(alias="from")
    target: Color = Field(alias="to")


class Outline(Model):
    color: Color
    connectivity: Annotated[Literal[4, 8], BeforeValidator(_integer)] = 8


class PixelOp(Model):
    pixel: Pixel


class PixelsOp(Model):
    pixels: Pixels


class LineOp(Model):
    line: Line


class RectOp(Model):
    rect: Rect


class EllipseOp(Model):
    ellipse: Ellipse


class PolygonOp(Model):
    polygon: Polygon


class FillOp(Model):
    fill: Fill


class ReplaceColorOp(Model):
    replace_color: ReplaceColor


class OutlineOp(Model):
    outline: Outline


def _operation_tag(value):
    if isinstance(value, Model):
        return "$" + next(iter(type(value).model_fields))
    if isinstance(value, dict) and len(value) == 1:
        return "$" + str(next(iter(value)))
    return None


OperationUnion = Annotated[
    Annotated[PixelOp, Tag("$pixel")]
    | Annotated[PixelsOp, Tag("$pixels")]
    | Annotated[LineOp, Tag("$line")]
    | Annotated[RectOp, Tag("$rect")]
    | Annotated[EllipseOp, Tag("$ellipse")]
    | Annotated[PolygonOp, Tag("$polygon")]
    | Annotated[FillOp, Tag("$fill")]
    | Annotated[ReplaceColorOp, Tag("$replace_color")]
    | Annotated[OutlineOp, Tag("$outline")],
    Discriminator(_operation_tag),
]


class Operation(RootModel[OperationUnion]):
    @property
    def kind(self) -> str:
        return next(iter(type(self.root).model_fields))

    @property
    def params(self) -> Model:
        return getattr(self.root, self.kind)


class Transform(Model):
    translate: Point = (0, 0)
    mirror_x: StrictBool = False
    mirror_y: StrictBool = False
    rotate: Annotated[Literal[0, 90, 180, 270], BeforeValidator(_integer)] = 0


class Layer(Model):
    name: Annotated[str, Field(min_length=1, max_length=128)]
    visible: StrictBool = True
    transform: Transform = Field(default_factory=Transform)
    operations: list[Operation] = Field(default_factory=list)


class Constraints(Model):
    max_colors: Annotated[StrictInt, Field(gt=0)] | None = None


class TransformOverride(Model):
    """Only specified transform fields replace inherited fields."""

    translate: Point | None = None
    mirror_x: StrictBool | None = None
    mirror_y: StrictBool | None = None
    rotate: Annotated[Literal[0, 90, 180, 270], BeforeValidator(_integer)] | None = None


class LayerOverride(Model):
    """A named layer patch; operations, if specified, replace the full list."""

    visible: StrictBool | None = None
    transform: TransformOverride | None = None
    operations: list[Operation] | None = None


class Frame(Model):
    extends: Name | None = None
    overrides: dict[Annotated[str, Field(min_length=1, max_length=128)], LayerOverride] = Field(default_factory=dict)


class Animation(Model):
    fps: Annotated[StrictInt, Field(gt=0, le=1000)]
    loop: StrictBool = True
    frames: Annotated[list[Name], Field(min_length=1)]


class Seam(Model):
    source: Name = Field(alias="from")
    target: Name = Field(alias="to")
    axis: Literal["x", "y"]


class Tileset(Model):
    columns: Annotated[StrictInt, Field(gt=0, le=4096)]
    tiles: Annotated[list[Name], Field(min_length=1)]
    seams: list[Seam] = Field(default_factory=list)


class Asset(Model):
    version: Annotated[Literal[1], BeforeValidator(_integer)] = 1
    canvas: Canvas
    palette: dict[Name, HexColor] = Field(default_factory=dict)
    layers: list[Layer] = Field(default_factory=list)
    constraints: Constraints = Field(default_factory=Constraints)
    frames: dict[Name, Frame] = Field(default_factory=dict)
    animations: dict[Name, Animation] = Field(default_factory=dict)
    tilesets: dict[Name, Tileset] = Field(default_factory=dict)
