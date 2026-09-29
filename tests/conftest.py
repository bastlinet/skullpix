import pytest

from skullpix import Asset


@pytest.fixture
def make_asset():
    def make(operations=(), *, size=(5, 5), layers=None, **kwargs):
        data = {"canvas": {"width": size[0], "height": size[1]},
                "palette": {"ink": "#112233", "red": "#ff0000", "clear": "#00000000"},
                "layers": layers if layers is not None else [{"name": "main", "operations": list(operations)}]}
        data.update(kwargs)
        return Asset.model_validate(data)
    return make


def occupied(image):
    return {(x, y) for y in range(image.height) for x in range(image.width)
            if image.getpixel((x, y))[3] > 0}


def matrix(image):
    points = occupied(image)
    return ["".join("#" if (x, y) in points else "." for x in range(image.width))
            for y in range(image.height)]
