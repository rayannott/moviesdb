"""FastAPI application for the movies database."""

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from starlette.requests import Request

from src.applications.api.routers import entries, stats, tags, watchlist
from src.dependencies import Container
from src.exceptions import (
    DuplicateEntryException,
    EntryNotFoundException,
    MalformedEntryException,
)


def create_app(container: Container) -> FastAPI:
    """Build a FastAPI instance with services from the given DI container."""
    app = FastAPI(
        title="MoviesDB API",
        description="REST API for the movies and series database",
        version="1.0.0",
        root_path="/api",
    )

    app.state.entry_service = container.entry_service()
    app.state.watchlist_service = container.watchlist_service()
    app.state.image_service = container.image_service()

    @app.exception_handler(EntryNotFoundException)
    async def not_found_handler(
        request: Request, exc: EntryNotFoundException
    ) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.exception_handler(MalformedEntryException)
    async def malformed_handler(
        request: Request, exc: MalformedEntryException
    ) -> JSONResponse:
        return JSONResponse(status_code=422, content={"detail": str(exc)})

    @app.exception_handler(DuplicateEntryException)
    async def duplicate_handler(
        request: Request, exc: DuplicateEntryException
    ) -> JSONResponse:
        return JSONResponse(status_code=409, content={"detail": str(exc)})

    app.include_router(entries.router)
    app.include_router(watchlist.router)
    app.include_router(tags.router)
    app.include_router(stats.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
