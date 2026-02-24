"""Entries API router."""

from fastapi import APIRouter, Depends, Query

from src.applications.api.auth import (
    AuthUser,
    UserRole,
    get_current_user,
    require_admin,
)
from src.applications.api.dependencies import get_entry_service
from src.applications.api.schemas import (
    EntryCreateRequest,
    EntryResponse,
    MessageResponse,
)
from src.models.entry import Entry, EntryType
from src.services.entry_service import EntryService

from loguru import logger

router = APIRouter(prefix="/entries", tags=["entries"])


def _to_response(entry: Entry, *, include_private: bool = True) -> EntryResponse:
    return EntryResponse(
        id=entry.id,
        title=entry.title,
        rating=entry.rating,
        date=entry.date,
        type=entry.type,
        notes=entry.notes if include_private else "",
        tags=sorted(entry.tags),
        image_ids=sorted(entry.image_ids) if include_private else [],
    )


@router.get("/", response_model=list[EntryResponse])
def list_entries(
    user: AuthUser = Depends(get_current_user),
    svc: EntryService = Depends(get_entry_service),
    n: int = Query(default=0, description="Limit results (0 = all)"),
    entry_type: EntryType | None = Query(default=None),
    tags: list[str] | None = Query(default=None),
) -> list[EntryResponse]:
    logger.info(
        f"[{user}] Listing entries with n={n}, entry_type={entry_type}, tags={tags}"
    )
    entries = svc.get_entries()
    if entry_type is not None:
        entries = [e for e in entries if e.type == entry_type]
    if tags is not None:
        entries = [e for e in entries if any(tag in e.tags for tag in tags)]
    if n > 0:
        entries = entries[-n:]
    private = user.role == UserRole.ADMIN
    return [_to_response(e, include_private=private) for e in entries]


@router.get("/{entry_id}", response_model=EntryResponse)
def get_entry(
    entry_id: str,
    user: AuthUser = Depends(get_current_user),
    svc: EntryService = Depends(get_entry_service),
) -> EntryResponse:
    logger.info(f"[{user}] Getting entry {entry_id}")
    private = user.role == UserRole.ADMIN
    return _to_response(svc.get_entry(entry_id), include_private=private)


@router.post("/", response_model=EntryResponse, status_code=201)
def create_entry(
    req: EntryCreateRequest,
    _admin: AuthUser = Depends(require_admin),
    svc: EntryService = Depends(get_entry_service),
) -> EntryResponse:
    logger.info(f"[{_admin}] Creating entry {req.title}")
    entry = Entry(
        title=req.title,
        rating=req.rating,
        date=req.date,
        type=req.type,
        notes=req.notes,
    )
    created = svc.add_entry(entry)
    svc.remove_from_watchlist_on_add(created)
    return _to_response(created)


@router.delete("/{entry_id}", response_model=MessageResponse)
def delete_entry(
    entry_id: str,
    _admin: AuthUser = Depends(require_admin),
    svc: EntryService = Depends(get_entry_service),
) -> MessageResponse:
    logger.info(f"[{_admin}] Deleting entry {entry_id}")
    svc.delete_entry(entry_id)
    return MessageResponse(message=f"Entry {entry_id} deleted")


@router.get("/search/{title}", response_model=list[EntryResponse])
def search_entries(
    title: str,
    user: AuthUser = Depends(get_current_user),
    svc: EntryService = Depends(get_entry_service),
) -> list[EntryResponse]:
    logger.info(f"[{user}] Searching entries for {title}")
    exact = svc.find_exact_matches(title)
    sub = svc.find_substring_matches(title)
    all_results = [e for _, e in exact + sub]
    private = user.role == UserRole.ADMIN
    return [_to_response(e, include_private=private) for e in all_results]


@router.get("/random/", response_model=list[EntryResponse])
def random_entries(
    user: AuthUser = Depends(get_current_user),
    svc: EntryService = Depends(get_entry_service),
    n: int = Query(default=1),
    tag: str | None = Query(default=None),
) -> list[EntryResponse]:
    logger.info(f"[{user}] Getting random entries with n={n}, tag={tag}")
    entries = svc.get_random_entries(n, tag)
    private = user.role == UserRole.ADMIN
    return [_to_response(e, include_private=private) for e in entries]
