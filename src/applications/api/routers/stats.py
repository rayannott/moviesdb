"""Stats API router."""

from statistics import mean

from fastapi import APIRouter, Depends

from src.applications.api.auth import AuthUser, get_current_user
from src.applications.api.dependencies import get_entry_service
from src.applications.api.schemas import StatsResponse
from src.services.entry_service import EntryService

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("/", response_model=StatsResponse)
def get_stats(
    _user: AuthUser = Depends(get_current_user),
    svc: EntryService = Depends(get_entry_service),
) -> StatsResponse:
    stats = svc.get_stats()
    return StatsResponse(
        total_entries=stats.total,
        movie_count=len(stats.movie_ratings),
        series_count=len(stats.series_ratings),
        avg_movie_rating=mean(stats.movie_ratings) if stats.movie_ratings else 0.0,
        avg_series_rating=mean(stats.series_ratings) if stats.series_ratings else 0.0,
        watchlist_count=stats.watchlist_count,
        unique_titles=len(stats.groups),
    )
