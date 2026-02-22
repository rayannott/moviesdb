"""Stats API router."""

from statistics import mean

from fastapi import APIRouter

from src.applications.api.schemas import StatsResponse
from src.services.entry_service import EntryService

router = APIRouter(prefix="/stats", tags=["stats"])

_entry_svc: EntryService | None = None


def init(entry_service: EntryService) -> None:
    global _entry_svc
    _entry_svc = entry_service


def _svc() -> EntryService:
    assert _entry_svc is not None, "EntryService not initialized"
    return _entry_svc


@router.get("/", response_model=StatsResponse)
def get_stats() -> StatsResponse:
    stats = _svc().get_stats()
    return StatsResponse(
        total_entries=stats.total,
        movie_count=len(stats.movie_ratings),
        series_count=len(stats.series_ratings),
        avg_movie_rating=mean(stats.movie_ratings) if stats.movie_ratings else 0.0,
        avg_series_rating=mean(stats.series_ratings) if stats.series_ratings else 0.0,
        watchlist_count=stats.watchlist_count,
        unique_titles=len(stats.groups),
    )
