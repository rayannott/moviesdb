"""Home screen -- stats dashboard shown on launch."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Footer, Static

from src.applications.fulltui.widgets.stats_panel import StatsPanel
from src.services.entry_service import StatsResult

if TYPE_CHECKING:
    from src.applications.fulltui.app import FullTUIApp


class HomeScreen(Screen):
    """Default view with a centered statistics panel."""

    app: "FullTUIApp"

    def compose(self) -> ComposeResult:
        yield Container(
            Static("Loading...", id="home-loading"),
            id="home-center",
        )
        yield Footer()

    def on_mount(self) -> None:
        self._load_stats()

    @work(thread=True, exclusive=True)
    def _load_stats(self) -> None:
        stats = self.app.entry_svc.get_stats()
        self.app.call_from_thread(self._render_stats, stats)

    def _render_stats(self, stats: StatsResult) -> None:
        center = self.query_one("#home-center")
        center.remove_children()
        center.mount(StatsPanel(stats))

    def refresh_data(self) -> None:
        """Reload stats from the database."""
        self._load_stats()
