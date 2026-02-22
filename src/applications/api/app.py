"""FastAPI application for the movies database."""

from fastapi import FastAPI

from src.applications.api.routers import entries, stats, tags, watchlist
from src.dependencies import Container


def create_app() -> FastAPI:
    """Create and configure the FastAPI application with DI container."""
    container = Container()

    app = FastAPI(
        title="MoviesDB API",
        description="REST API for the movies and series database",
        version="1.0.0",
    )

    entry_svc = container.entry_service()
    watchlist_svc = container.watchlist_service()

    entries.init(entry_svc)
    watchlist.init(watchlist_svc)
    tags.init(entry_svc)
    stats.init(entry_svc)

    app.include_router(entries.router)
    app.include_router(watchlist.router)
    app.include_router(tags.router)
    app.include_router(stats.router)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
