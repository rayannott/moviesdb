"""Watchlist API router."""

from fastapi import APIRouter, HTTPException

from src.applications.api.schemas import (
    MessageResponse,
    WatchlistAddRequest,
    WatchlistItemResponse,
)
from src.services.watchlist_service import WatchlistService

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

_watchlist_svc: WatchlistService | None = None


def init(watchlist_service: WatchlistService) -> None:
    global _watchlist_svc
    _watchlist_svc = watchlist_service


def _svc() -> WatchlistService:
    assert _watchlist_svc is not None, "WatchlistService not initialized"
    return _watchlist_svc


@router.get("/", response_model=list[WatchlistItemResponse])
def list_watchlist() -> list[WatchlistItemResponse]:
    items = _svc().get_items()
    return [WatchlistItemResponse(title=t, is_series=s) for t, s in items]


@router.post("/", response_model=MessageResponse, status_code=201)
def add_to_watchlist(req: WatchlistAddRequest) -> MessageResponse:
    if _svc().contains(req.title, req.is_series):
        raise HTTPException(status_code=409, detail="Already in watchlist")
    _svc().add(req.title, req.is_series)
    return MessageResponse(message=f"Added '{req.title}' to watchlist")


@router.delete("/", response_model=MessageResponse)
def remove_from_watchlist(title: str, is_series: bool = False) -> MessageResponse:
    if _svc().remove(title, is_series):
        return MessageResponse(message=f"Removed '{title}' from watchlist")
    raise HTTPException(status_code=404, detail="Not found in watchlist")
