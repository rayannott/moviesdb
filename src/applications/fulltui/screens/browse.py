"""Browse screen -- paginated entry list with keyboard selection."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Static

from src.applications.fulltui.widgets.entry_card import EntryCard
from src.models.entry import Entry

if TYPE_CHECKING:
    from src.applications.fulltui.app import FullTUIApp

PAGE_SIZE = 15


class BrowseScreen(Screen):
    """Paginated entry browser with arrow-key selection."""

    app: "FullTUIApp"

    BINDINGS = [
        Binding("pageup", "prev_page", "Prev page"),
        Binding("pagedown", "next_page", "Next page"),
        Binding("up", "select_prev", "Up", show=False),
        Binding("down", "select_next", "Down", show=False),
        Binding("ctrl+a", "expand", "Expand entry"),
        Binding("escape", "go_home", "Back"),
    ]

    page = reactive(0)
    selected_idx = reactive(0)

    def __init__(self, **kwargs) -> None:  # type: ignore[override]
        super().__init__(**kwargs)
        self._entries: list[Entry] = []
        self._gen = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="browse-wrapper"):
            yield Static("", id="page-indicator")
            yield VerticalScroll(id="entries-list")
        yield Footer()

    def on_mount(self) -> None:
        self._load_entries()

    @work(thread=True)
    def _load_entries(self) -> None:
        entries = self.app.entry_svc.get_entries()
        self.app.call_from_thread(self._set_entries, entries)

    def _set_entries(self, entries: list[Entry]) -> None:
        self._entries = entries
        self.page = 0
        self.selected_idx = 0
        self._render_page()

    @property
    def _total_pages(self) -> int:
        return max(1, math.ceil(len(self._entries) / PAGE_SIZE))

    @property
    def _page_entries(self) -> list[Entry]:
        """Return entries for current page (most recent first)."""
        reversed_entries = list(reversed(self._entries))
        start = self.page * PAGE_SIZE
        return reversed_entries[start : start + PAGE_SIZE]

    def _render_page(self) -> None:
        self._gen += 1
        container = self.query_one("#entries-list", VerticalScroll)
        container.remove_children()

        gen = self._gen
        cards = [
            EntryCard(entry, id=f"card-{gen}-{i}")
            for i, entry in enumerate(self._page_entries)
        ]
        container.mount_all(cards)

        self.selected_idx = 0
        self._highlight_selected()
        self._update_indicator()

    def _update_indicator(self) -> None:
        indicator = self.query_one("#page-indicator", Static)
        total = len(self._entries)
        indicator.update(
            f" Page {self.page + 1}/{self._total_pages}  ({total} entries)"
        )

    def _highlight_selected(self) -> None:
        cards = list(self.query(EntryCard))
        for i, card in enumerate(cards):
            card.highlighted = i == self.selected_idx
        if cards:
            selected = cards[min(self.selected_idx, len(cards) - 1)]
            selected.scroll_visible()

    def action_next_page(self) -> None:
        if self.page < self._total_pages - 1:
            self.page += 1
            self.selected_idx = 0
            self._render_page()

    def action_prev_page(self) -> None:
        if self.page > 0:
            self.page -= 1
            self.selected_idx = 0
            self._render_page()

    def action_select_next(self) -> None:
        cards = list(self.query(EntryCard))
        if cards and self.selected_idx < len(cards) - 1:
            self.selected_idx += 1
            self._highlight_selected()

    def action_select_prev(self) -> None:
        if self.selected_idx > 0:
            self.selected_idx -= 1
            self._highlight_selected()

    def action_expand(self) -> None:
        cards = list(self.query(EntryCard))
        if not cards:
            return
        idx = min(self.selected_idx, len(cards) - 1)
        entry = cards[idx].entry
        from src.applications.fulltui.screens.detail import DetailScreen

        self.app.push_screen(DetailScreen(entry, self.app.entry_svc))

    def action_go_home(self) -> None:
        self.app.switch_mode("home")

    def refresh_data(self) -> None:
        """Reload entries from the database."""
        self._load_entries()
