"""Tests for the image service and ImageManager."""

import pytest

from src.dependencies import Container
from src.services.image_service import ImageService


@pytest.fixture(scope="module")
def image_service() -> ImageService:
    """Fixture to create an ImageService from the DI container."""
    container = Container()
    return container.image_service()


def test_image_service_create_manager_bare(image_service: ImageService) -> None:
    """A bare manager should have no entries."""
    manager = image_service.create_manager_bare()
    assert manager.entries == []
