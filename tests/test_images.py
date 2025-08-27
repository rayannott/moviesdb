import pytest

from src.obj.images_manager import ImagesStore


@pytest.fixture(scope="module")
def image_store_noentries():
    return ImagesStore([])


def test_image_store_noentries(image_store_noentries: ImagesStore):
    assert image_store_noentries.entries == []
