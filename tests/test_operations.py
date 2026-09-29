import pytest

from skullpix import render_asset
from conftest import occupied


def test_fill_only_interior_and_exact_target(make_asset):
    image = render_asset(make_asset([
        {"rect": {"box": [1, 1, 3, 3], "color": "ink", "fill": False}},
        {"fill": {"seed": [2, 2], "color": "red"}},
        {"fill": {"seed": [2, 2], "color": "red"}},
    ]))
    assert image.getpixel((2, 2)) == (255, 0, 0, 255)
    assert image.getpixel((1, 2)) == (17, 34, 51, 255)
    assert image.getpixel((0, 0)) == (0, 0, 0, 0)


def test_fill_is_four_connected(make_asset):
    image = render_asset(make_asset([
        {"pixels": {"points": [[0, 0], [1, 1]], "color": "ink"}},
        {"fill": {"seed": [0, 0], "color": "red"}},
    ], size=(2, 2)))
    assert image.getpixel((0, 0)) == (255, 0, 0, 255)
    assert image.getpixel((1, 1)) == (17, 34, 51, 255)


def test_fill_matches_alpha_and_layer_not_composite(make_asset):
    image = render_asset(make_asset(size=(2, 1), layers=[
        {"name": "bottom", "operations": [{"rect": {"box": [0, 0, 2, 1], "color": "red"}}]},
        {"name": "top", "operations": [
            {"pixel": {"at": [0, 0], "color": "#11223380"}},
            {"pixel": {"at": [1, 0], "color": "#112233ff"}},
            {"fill": {"seed": [0, 0], "color": "clear"}},
        ]},
    ]))
    assert image.getpixel((0, 0)) == (255, 0, 0, 255)
    assert image.getpixel((1, 0)) == (17, 34, 51, 255)


def test_fill_outside_canvas_has_no_effect(make_asset):
    with pytest.warns(UserWarning, match="W020"):
        assert occupied(render_asset(make_asset([{"fill": {"seed": [-1, 0], "color": "red"}}]))) == set()


def test_replace_color_exact_rgba_including_transparency(make_asset):
    image = render_asset(make_asset([
        {"pixel": {"at": [0, 0], "color": "#11223380"}},
        {"pixel": {"at": [1, 0], "color": "ink"}},
        {"replace_color": {"from": "ink", "to": "red"}},
        {"replace_color": {"from": "clear", "to": "ink"}},
    ], size=(3, 1)))
    assert image.getpixel((0, 0)) == (17, 34, 51, 128)
    assert image.getpixel((1, 0)) == (255, 0, 0, 255)
    assert image.getpixel((2, 0)) == (17, 34, 51, 255)


@pytest.mark.parametrize("connectivity,ring", [
    (4, {(1, 2), (2, 1), (3, 2), (2, 3)}),
    (8, {(1, 1), (2, 1), (3, 1), (1, 2), (3, 2), (1, 3), (2, 3), (3, 3)}),
])
def test_outline_uses_snapshot_and_keeps_occupied_rgba(make_asset, connectivity, ring):
    image = render_asset(make_asset([
        {"pixel": {"at": [2, 2], "color": "#ff000080"}},
        {"outline": {"color": "ink", "connectivity": connectivity}},
    ]))
    assert occupied(image) == ring | {(2, 2)}
    assert image.getpixel((2, 2)) == (255, 0, 0, 128)
    assert all(image.getpixel(point) == (17, 34, 51, 255) for point in ring)


def test_outline_empty_layer_is_empty(make_asset):
    assert occupied(render_asset(make_asset([{"outline": {"color": "ink"}}]))) == set()


@pytest.mark.parametrize("transform,expected", [
    ({"translate": [2, 1]}, {(3, 1), (4, 2)}),
    ({"translate": [-2, -1]}, {(0, 0)}),
    ({"mirror_x": True}, {(3, 0), (2, 1)}),
    ({"mirror_y": True}, {(1, 4), (2, 3)}),
    ({"rotate": 90}, {(4, 1), (3, 2)}),
    ({"rotate": 180}, {(3, 4), (2, 3)}),
    ({"rotate": 270}, {(0, 3), (1, 2)}),
    ({"mirror_x": True, "rotate": 90, "translate": [-1, -1]}, {(3, 2), (2, 1)}),
])
def test_transform_mappings(make_asset, transform, expected):
    asset = make_asset(layers=[{"name": "a", "transform": transform, "operations": [
        {"pixels": {"points": [[1, 0], [2, 1]], "color": "ink"}}]}])
    if transform.get("translate") == [-2, -1]:
        with pytest.warns(UserWarning, match="W020"):
            assert occupied(render_asset(asset)) == expected
    else:
        assert occupied(render_asset(asset)) == expected


def test_rotation_on_rectangular_canvas_swaps_dimensions_and_anchors_top_left(make_asset):
    asset = make_asset(size=(4, 2), layers=[{"name": "a", "transform": {"rotate": 90},
        "operations": [{"pixels": {"points": [[0, 0], [3, 1]], "color": "ink"}}]}])
    with pytest.warns(UserWarning, match="W020"):
        image = render_asset(asset)
    assert image.size == (4, 2)
    assert occupied(image) == {(1, 0)}


def test_translation_applies_after_rotation_before_clipping(make_asset):
    asset = make_asset(size=(4, 2), layers=[{"name": "a", "transform": {"rotate": 90, "translate": [0, -2]},
        "operations": [{"pixel": {"at": [3, 1], "color": "ink"}}]}])
    assert occupied(render_asset(asset)) == {(0, 1)}


@pytest.mark.parametrize("transform", [{"rotate": 45}, {"rotate": 90.0}, {"mirror_x": 1}, {"translate": [0.5, 1]}])
def test_invalid_transforms_rejected(make_asset, transform):
    with pytest.raises(ValueError):
        make_asset(layers=[{"name": "a", "transform": transform}])
