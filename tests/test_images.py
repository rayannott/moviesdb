import pytest

from src.obj.images_manager import ImagesStore


@pytest.fixture(scope="module")
def image_store_noentries():
    return ImagesStore([])


def test_image_store_noentries(image_store_noentries: ImagesStore):
    assert image_store_noentries.entries == []


def test_detect_duplicates(image_store_noentries: ImagesStore):
    hash_groups = image_store_noentries._group_by_etag_hash()
    for hash_val, s3_ids in hash_groups.items():
        assert len(s3_ids) == 1, f"Duplicate images found for hash {hash_val}: {s3_ids}"
