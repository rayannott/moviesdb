"""API request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field

from src.models.entry import EntryType


class EntryResponse(BaseModel):
    """Entry response for API consumers."""

    id: str
    title: str
    rating: float
    date: datetime | None = None
    type: EntryType = EntryType.MOVIE
    notes: str = ""
    tags: list[str] = Field(default_factory=list)
    image_ids: list[str] = Field(default_factory=list)


class EntryCreateRequest(BaseModel):
    """Request body for creating a new entry."""

    title: str
    rating: float
    date: datetime | None = None
    type: EntryType = EntryType.MOVIE
    notes: str = ""


class WatchlistItemResponse(BaseModel):
    """Watchlist item response."""

    title: str
    is_series: bool


class WatchlistAddRequest(BaseModel):
    """Request body for adding to watchlist."""

    title: str
    is_series: bool = False


class TagStatsResponse(BaseModel):
    """Tag statistics response."""

    tag: str
    count: int
    avg_rating: float


class StatsResponse(BaseModel):
    """Overall stats response."""

    total_entries: int
    movie_count: int
    series_count: int
    avg_movie_rating: float
    avg_series_rating: float
    watchlist_count: int
    unique_titles: int


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str
    success: bool = True
