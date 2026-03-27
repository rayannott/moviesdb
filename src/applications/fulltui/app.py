"""Full-screen Textual TUI application and factory."""

from __future__ import annotations

from textual.app import App
from textual.binding import Binding

from src.applications.fulltui.screens.browse import BrowseScreen
from src.applications.fulltui.screens.home import HomeScreen
from src.dependencies import Container
from src.models.entry import Entry
from src.services.entry_service import EntryService
from src.services.watchlist_service import WatchlistService


class FullTUIApp(App):
    """Movies & series personal database -- full TUI."""

    CSS_PATH = "fulltui.tcss"

    MODES = {
        "home": HomeScreen,
        "browse": BrowseScreen,
    }
    DEFAULT_MODE = "home"

    BINDINGS = [
        Binding("enter", "switch_mode('browse')", "Browse", show=True),
        Binding("ctrl+n", "add_entry", "Add entry", show=True),
        Binding("q", "quit", "Quit", show=True),
        Binding("ctrl+q", "quit", "Quit", show=False),
    ]

    def __init__(
        self,
        entry_service: EntryService,
        watchlist_service: WatchlistService,
    ) -> None:
        super().__init__()
        self.entry_svc = entry_service
        self.watchlist_svc = watchlist_service
        self.theme = "textual-dark"

    def check_action(self, action: str, parameters: tuple) -> bool:  # type: ignore[override]
        """Prevent switching to the already active mode."""
        if action == "switch_mode" and parameters:
            if parameters[0] == self.current_mode:
                return False
        return True

    def action_add_entry(self) -> None:
        """Push the add-entry modal screen."""
        from src.applications.fulltui.screens.add_entry import AddEntryScreen

        def _on_dismiss(result: Entry | None) -> None:
            if result is not None:
                self._refresh_current_screen()

        self.push_screen(AddEntryScreen(), callback=_on_dismiss)

    def _refresh_current_screen(self) -> None:
        """Refresh data on the currently active screen if it supports it."""
        screen = self.screen
        if hasattr(screen, "refresh_data"):
            screen.refresh_data()  # type: ignore[attr-defined]


def create_fulltui_app(container: Container) -> FullTUIApp:
    """Build the full TUI app from the DI container."""
    return FullTUIApp(
        entry_service=container.entry_service(),
        watchlist_service=container.watchlist_service(),
    )
