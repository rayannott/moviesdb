"""Tags API router."""

from statistics import mean

from fastapi import APIRouter, Depends

from src.applications.api.auth import AuthUser, get_current_user
from src.applications.api.dependencies import get_entry_service
from src.applications.api.schemas import TagStatsResponse
from src.services.entry_service import EntryService

router = APIRouter(prefix="/tags", tags=["tags"])


@router.get("/", response_model=list[TagStatsResponse])
def list_tags(
    _admin: AuthUser = Depends(get_current_user),
    svc: EntryService = Depends(get_entry_service),
) -> list[TagStatsResponse]:
    tags = svc.get_tags()
    return sorted(
        [
            TagStatsResponse(
                tag=tag,
                count=len(entries),
                avg_rating=mean(e.rating for e in entries),
            )
            for tag, entries in tags.items()
        ],
        key=lambda t: t.count,
        reverse=True,
    )
