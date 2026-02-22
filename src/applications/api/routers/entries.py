"""Entries API router."""

from fastapi import APIRouter, HTTPException, Query

from src.applications.api.schemas import (
    EntryCreateRequest,
    EntryResponse,
    MessageResponse,
)
from src.models.entry import Entry
from src.services.entry_service import EntryService

router = APIRouter(prefix="/entries", tags=["entries"])

_entry_svc: EntryService | None = None


def init(entry_service: EntryService) -> None:
    global _entry_svc
    _entry_svc = entry_service


def _svc() -> EntryService:
    assert _entry_svc is not None, "EntryService not initialized"
    return _entry_svc


def _to_response(entry: Entry) -> EntryResponse:
    return EntryResponse(
        id=entry.id,
        title=entry.title,
        rating=entry.rating,
        date=entry.date,
        type=entry.type,
        notes=entry.notes,
        tags=sorted(entry.tags),
        image_ids=sorted(entry.image_ids),
        is_series=entry.is_series,
    )


@router.get("/", response_model=list[EntryResponse])
def list_entries(
    n: int = Query(default=0, description="Limit results (0 = all)"),
    series_only: bool = Query(default=False),
    movies_only: bool = Query(default=False),
) -> list[EntryResponse]:
    entries = _svc().get_entries()
    if series_only:
        entries = [e for e in entries if e.is_series]
    elif movies_only:
        entries = [e for e in entries if not e.is_series]
    if n > 0:
        entries = entries[-n:]
    return [_to_response(e) for e in entries]


@router.get("/{entry_id}", response_model=EntryResponse)
def get_entry(entry_id: str) -> EntryResponse:
    try:
        entry = _svc().get_entry(entry_id)
    except Exception:
        raise HTTPException(status_code=404, detail="Entry not found")
    return _to_response(entry)


@router.post("/", response_model=EntryResponse, status_code=201)
def create_entry(req: EntryCreateRequest) -> EntryResponse:
    entry = Entry(
        title=req.title,
        rating=req.rating,
        date=req.date,
        type=req.type,
        notes=req.notes,
    )
    created = _svc().add_entry(entry)
    _svc().remove_from_watchlist_on_add(created)
    return _to_response(created)


@router.delete("/{entry_id}", response_model=MessageResponse)
def delete_entry(entry_id: str) -> MessageResponse:
    if _svc().delete_entry(entry_id):
        return MessageResponse(message=f"Entry {entry_id} deleted")
    raise HTTPException(status_code=404, detail="Entry not found")


@router.get("/search/{title}", response_model=list[EntryResponse])
def search_entries(title: str) -> list[EntryResponse]:
    exact = _svc().find_exact_matches(title)
    sub = _svc().find_substring_matches(title)
    all_results = [e for _, e in exact + sub]
    return [_to_response(e) for e in all_results]


@router.get("/random/", response_model=list[EntryResponse])
def random_entries(
    n: int = Query(default=1), tag: str | None = Query(default=None)
) -> list[EntryResponse]:
    entries = _svc().get_random_entries(n, tag)
    return [_to_response(e) for e in entries]
