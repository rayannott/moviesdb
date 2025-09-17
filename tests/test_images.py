import pytest

from src.obj.image import ImageManager


@pytest.fixture(scope="module")
def image_store_noentries():
    return ImageManager([])


def test_image_store_noentries(image_store_noentries: ImageManager):
    assert image_store_noentries.entries == []
