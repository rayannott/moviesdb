"""Search screen -- instant in-memory search with live results."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer, Input, Static

from src.applications.fulltui.widgets.entry_card import EntryCard
from src.models.entry import Entry

if TYPE_CHECKING:
    from src.applications.fulltui.app import FullTUIApp


MAX_DISPLAYED = 50


class SearchScreen(Screen):
    """Instant in-memory search with keyboard navigation."""

    app: "FullTUIApp"

    BINDINGS = [
        Binding("up", "select_prev", "Up", show=False),
        Binding("down", "select_next", "Down", show=False),
        Binding("ctrl+a", "expand", "Expand entry"),
        Binding("escape", "go_home", "Back"),
        Binding("ctrl+f", "toggle_input", "Toggle search", show=False),
    ]

    selected_idx = reactive(0)
    _search_active = reactive(True)

    def __init__(self, **kwargs) -> None:  # type: ignore[override]
        super().__init__(**kwargs)
        self._all_entries: list[Entry] = []
        self._search_index: list[tuple[str, str, Entry]] = []
        self._results: list[Entry] = []
        self._gen = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="search-wrapper"):
            yield Input(placeholder="search...", id="search-input")
            yield Static("", id="search-status")
            yield VerticalScroll(id="search-results")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#search-input", Input).focus()
        self._prefetch()

    @work(thread=True)
    def _prefetch(self) -> None:
        """Load all entries once into memory."""
        entries = self.app.entry_svc.get_entries()
        self.app.call_from_thread(self._set_entries, entries)

    def _set_entries(self, entries: list[Entry]) -> None:
        self._all_entries = entries
        self._search_index = [
            (e.title.lower(), e.notes.lower(), e) for e in entries
        ]

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "search-input":
            return
        self._do_search()

    def _do_search(self) -> None:
        query = self.query_one("#search-input", Input).value.strip().lower()
        if not query:
            self._results = []
            self._render_results()
            return

        self._results = [
            entry for title_l, notes_l, entry in self._search_index
            if query in title_l or query in notes_l
        ]
        self.selected_idx = 0
        self._render_results()

    def _render_results(self) -> None:
        self._gen += 1
        container = self.query_one("#search-results", VerticalScroll)
        container.remove_children()

        status = self.query_one("#search-status", Static)
        total = len(self._results)
        if not self._results:
            query = self.query_one("#search-input", Input).value.strip()
            if query:
                status.update(" No results")
            else:
                status.update("")
            return

        shown = min(total, MAX_DISPLAYED)
        suffix = f"  (showing {shown})" if total > MAX_DISPLAYED else ""
        status.update(f" {total} results{suffix}")

        gen = self._gen
        cards = [
            EntryCard(entry, id=f"scard-{gen}-{i}")
            for i, entry in enumerate(self._results[:MAX_DISPLAYED])
        ]
        container.mount_all(cards)
        self._highlight_selected()

    def _highlight_selected(self) -> None:
        cards = list(self.query(EntryCard))
        for i, card in enumerate(cards):
            card.highlighted = i == self.selected_idx
        if cards:
            selected = cards[min(self.selected_idx, len(cards) - 1)]
            selected.scroll_visible()

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

    def action_toggle_input(self) -> None:
        """Toggle search input: hide it and keep results selectable, or re-show."""
        inp = self.query_one("#search-input", Input)
        if self._search_active:
            inp.add_class("hidden")
            self._search_active = False
        else:
            inp.remove_class("hidden")
            self._search_active = True
            inp.focus()

    def action_go_home(self) -> None:
        self.app.switch_mode("home")
