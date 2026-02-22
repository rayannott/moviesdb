"""Tags API router."""

from statistics import mean

from fastapi import APIRouter

from src.applications.api.schemas import TagStatsResponse
from src.services.entry_service import EntryService

router = APIRouter(prefix="/tags", tags=["tags"])

_entry_svc: EntryService | None = None


def init(entry_service: EntryService) -> None:
    global _entry_svc
    _entry_svc = entry_service


def _svc() -> EntryService:
    assert _entry_svc is not None, "EntryService not initialized"
    return _entry_svc


@router.get("/", response_model=list[TagStatsResponse])
def list_tags() -> list[TagStatsResponse]:
    tags = _svc().get_tags()
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
