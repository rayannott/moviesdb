"""Watchlist API router."""

from fastapi import APIRouter, Depends

from src.applications.api.auth import AuthUser, get_current_user, require_admin
from src.applications.api.dependencies import get_watchlist_service
from src.applications.api.schemas import (
    MessageResponse,
    WatchlistAddRequest,
    WatchlistItemResponse,
)
from src.services.watchlist_service import WatchlistService

from loguru import logger

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


@router.get("/", response_model=list[WatchlistItemResponse])
def list_watchlist(
    user: AuthUser = Depends(get_current_user),
    svc: WatchlistService = Depends(get_watchlist_service),
) -> list[WatchlistItemResponse]:
    logger.info(f"[{user}] Listing watchlist")
    items = svc.get_items()
    return [WatchlistItemResponse(title=t, is_series=s) for t, s in items]


@router.post("/", response_model=MessageResponse, status_code=201)
def add_to_watchlist(
    req: WatchlistAddRequest,
    user: AuthUser = Depends(require_admin),
    svc: WatchlistService = Depends(get_watchlist_service),
) -> MessageResponse:
    logger.info(f"[{user}] Adding to watchlist {req.title}")
    svc.add(req.title, req.is_series)
    return MessageResponse(message=f"Added '{req.title}' to watchlist")


@router.delete("/", response_model=MessageResponse)
def remove_from_watchlist(
    title: str,
    user: AuthUser = Depends(require_admin),
    is_series: bool = False,
    svc: WatchlistService = Depends(get_watchlist_service),
) -> MessageResponse:
    logger.info(f"[{user}] Removing from watchlist {title}")
    svc.remove(title, is_series)
    return MessageResponse(message=f"Removed '{title}' from watchlist")
