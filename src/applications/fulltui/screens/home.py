"""Home screen -- stats dashboard shown on launch."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, LoadingIndicator

from src.applications.fulltui.widgets.stats_panel import (
    RatingDistributionPanel,
    StatsPanel,
)
from src.services.entry_service import StatsResult

if TYPE_CHECKING:
    from src.applications.fulltui.app import FullTUIApp


class HomeScreen(Screen):
    """Default view with compact statistics in a centered grid."""

    app: "FullTUIApp"

    def compose(self) -> ComposeResult:
        yield Container(
            LoadingIndicator(id="home-loader"),
            id="home-grid",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_stats()

    @work(thread=True)
    def _load_stats(self) -> None:
        stats = self.app.entry_svc.get_stats()
        all_ratings = stats.movie_ratings + stats.series_ratings
        self.app.call_from_thread(self._render_stats, stats, all_ratings)

    def _render_stats(
        self,
        stats: StatsResult,
        all_ratings: list[float],
    ) -> None:
        grid = self.query_one("#home-grid")
        loader = grid.query("#home-loader")
        for w in loader:
            w.remove()

        panel = StatsPanel(stats, id="stats-panel")
        grid.mount(panel)

        if all_ratings:
            dist = RatingDistributionPanel(all_ratings, id="dist-panel")
            grid.mount(dist)

    def refresh_data(self) -> None:
        """Reload stats from the database."""
        grid = self.query_one("#home-grid")
        grid.remove_children()
        grid.mount(LoadingIndicator(id="home-loader"))
        self._load_stats()
