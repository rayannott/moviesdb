"""FastAPI dependency getters backed by app.state."""

from functools import lru_cache

from fastapi import Request

from src.services.entry_service import EntryService
from src.services.image_service import ImageService
from src.services.watchlist_service import WatchlistService
from src.settings import Settings


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]


def get_entry_service(request: Request) -> EntryService:
    return request.app.state.entry_service


def get_watchlist_service(request: Request) -> WatchlistService:
    return request.app.state.watchlist_service


def get_image_service(request: Request) -> ImageService:
    return request.app.state.image_service
