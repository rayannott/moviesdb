import pytest

from src.obj.images_manager import ImagesStore


@pytest.fixture(scope="module")
def image_store_noentries():
    return ImagesStore([])


def test_image_store_noentries(image_store_noentries: ImagesStore):
    assert image_store_noentries.entries == []


@pytest.mark.skip(reason="Will not check in testing: not a codebase issue")
def test_detect_duplicates(image_store_noentries: ImagesStore):
    # TODO: move this functionality to the app (e.g. check on startup)
    hash_groups = image_store_noentries._group_by_etag_hash()
    for hash_val, s3_ids in hash_groups.items():
        assert len(s3_ids) == 1, f"Duplicate images found for hash {hash_val}: {s3_ids}"
