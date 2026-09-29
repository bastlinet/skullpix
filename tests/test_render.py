import pytest

from skullpix import render_asset
from conftest import matrix, occupied


def test_empty_canvas_is_rgba_transparent(make_asset):
    image = render_asset(make_asset(size=(2, 3)))
    assert image.mode == "RGBA"
    assert image.size == (2, 3)
    assert occupied(image) == set()


def test_pixels_and_single_pixel(make_asset):
    image = render_asset(make_asset([
        {"pixels": {"points": [[0, 1], [2, 3]], "color": "ink"}},
        {"pixel": {"at": [4, 2], "color": "#ff000080"}},
    ]))
    assert occupied(image) == {(0, 1), (2, 3), (4, 2)}
    assert image.getpixel((4, 2)) == (255, 0, 0, 128)


@pytest.mark.parametrize("end,expected", [
    ([4, 0], ["#####", ".....", ".....", ".....", "....."]),
    ([0, 4], ["#...."] * 5),
    ([4, 4], ["#....", ".#...", "..#..", "...#.", "....#"]),
    ([4, 2], ["#....", ".##..", "...##", ".....", "....."]),
    ([0, 0], ["#....", ".....", ".....", ".....", "....."]),
])
def test_bresenham_includes_endpoints_and_is_direction_independent(make_asset, end, expected):
    for start, stop in (([0, 0], end), (end, [0, 0])):
        image = render_asset(make_asset([{"line": {"from": start, "to": stop, "color": "ink"}}]))
        assert matrix(image) == expected


@pytest.mark.parametrize("fill,expected", [
    (True, [".....", ".###.", ".###.", ".###.", "....."]),
    (False, [".....", ".###.", ".#.#.", ".###.", "....."]),
])
def test_rect_box_uses_dimensions(make_asset, fill, expected):
    image = render_asset(make_asset([{"rect": {"box": [1, 1, 3, 3], "color": "ink", "fill": fill}}]))
    assert matrix(image) == expected


@pytest.mark.parametrize("kind", ["rect", "ellipse"])
def test_one_pixel_boxes(make_asset, kind):
    image = render_asset(make_asset([{kind: {"box": [2, 3, 1, 1], "color": "ink"}}]))
    assert occupied(image) == {(2, 3)}


@pytest.mark.parametrize("fill,expected", [
    (True, [".###.", "#####", "#####", "#####", ".###."]),
    (False, [".###.", "#...#", "#...#", "#...#", ".###."]),
])
def test_ellipse_has_no_anti_aliasing(make_asset, fill, expected):
    image = render_asset(make_asset([{"ellipse": {"box": [0, 0, 5, 5], "color": "ink", "fill": fill}}]))
    assert matrix(image) == expected
    assert {pixel[3] for pixel in image.get_flattened_data()} <= {0, 255}


@pytest.mark.parametrize("fill,expected", [
    (True, ["#####", "####.", "###..", "##...", "#...."]),
    (False, ["#####", "#..#.", "#.#..", "##...", "#...."]),
])
def test_polygon_closed_outline_and_fill(make_asset, fill, expected):
    image = render_asset(make_asset([{"polygon": {
        "points": [[0, 0], [4, 0], [0, 4]], "color": "ink", "fill": fill}}]))
    assert matrix(image) == expected


def test_layers_source_over_and_visibility(make_asset):
    image = render_asset(make_asset(size=(1, 1), layers=[
        {"name": "bottom", "operations": [{"pixel": {"at": [0, 0], "color": "red"}}]},
        {"name": "middle", "operations": [{"pixel": {"at": [0, 0], "color": "#0000ff80"}}]},
        {"name": "hidden", "visible": False, "operations": [{"pixel": {"at": [0, 0], "color": "ink"}}]},
    ]))
    assert image.getpixel((0, 0)) == (127, 0, 128, 255)


def test_drawing_replaces_rgba_and_transparent_erases_within_layer(make_asset):
    image = render_asset(make_asset([
        {"rect": {"box": [0, 0, 2, 1], "color": "red"}},
        {"pixel": {"at": [0, 0], "color": "#0000ff80"}},
        {"pixel": {"at": [1, 0], "color": "clear"}},
    ]))
    assert image.getpixel((0, 0)) == (0, 0, 255, 128)
    assert image.getpixel((1, 0)) == (0, 0, 0, 0)


def test_background_and_independent_calls(make_asset):
    asset = make_asset(canvas={"width": 2, "height": 2, "background": "red"})
    first = render_asset(asset)
    first.putpixel((0, 0), (0, 0, 0, 0))
    assert render_asset(asset).getpixel((0, 0)) == (255, 0, 0, 255)


def test_primitive_clips_safely(make_asset):
    asset = make_asset([
        {"rect": {"box": [-1, -1, 3, 3], "color": "ink"}},
        {"pixel": {"at": [5, 5], "color": "red"}},
        {"line": {"from": [-2, 4], "to": [7, 4], "color": "ink"}},
    ])
    with pytest.warns(UserWarning, match="W020"):
        assert matrix(render_asset(asset)) == ["##...", "##...", ".....", ".....", "#####"]
