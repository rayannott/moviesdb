"""Browse screen -- paginated entries with inline fuzzy search."""

from __future__ import annotations

import math
import re
from typing import TYPE_CHECKING

from rapidfuzz import fuzz
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

PAGE_SIZE = 15
FUZZY_CUTOFF = 45


def _search_score(query: str, title_lower: str) -> float:
    """Score a title against a query, prioritising exact/whole-word matches."""
    if title_lower == query:
        return 300.0
    if re.search(r"\b" + re.escape(query) + r"\b", title_lower):
        return 200.0 + fuzz.ratio(query, title_lower)
    return float(fuzz.WRatio(query, title_lower))


class BrowseScreen(Screen):
    """Paginated entry browser with inline search."""

    app: "FullTUIApp"

    BINDINGS = [
        Binding("pageup", "prev_page", "Prev page"),
        Binding("pagedown", "next_page", "Next page"),
        Binding("up", "select_prev", "Up", show=False, priority=True),
        Binding("down", "select_next", "Down", show=False, priority=True),
        Binding("ctrl+a", "expand", "Expand entry", priority=True),
        Binding("escape", "back", "Back"),
    ]

    page = reactive(0)
    selected_idx = reactive(-1)

    def __init__(self, **kwargs) -> None:  # type: ignore[override]
        super().__init__(**kwargs)
        self._entries: list[Entry] = []
        self._search_index: list[tuple[str, str, Entry]] = []
        self._filtered: list[Entry] | None = None
        self._gen = 0

    def compose(self) -> ComposeResult:
        with Vertical(id="browse-wrapper"):
            yield Input(placeholder="search...", id="search-input")
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
        self._entries = sorted(entries, reverse=True)
        self._titles_lower = [e.title.lower() for e in self._entries]
        self.page = 0
        self.selected_idx = -1
        self._render_page()

    # ── Active entry list (search or full) ──

    @property
    def _active_entries(self) -> list[Entry]:
        """Filtered results when searching, otherwise all entries sorted."""
        if self._filtered is not None:
            return self._filtered
        return self._entries

    @property
    def _total_pages(self) -> int:
        return max(1, math.ceil(len(self._active_entries) / PAGE_SIZE))

    @property
    def _page_entries(self) -> list[Entry]:
        start = self.page * PAGE_SIZE
        return self._active_entries[start : start + PAGE_SIZE]

    # ── Search ──

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "search-input":
            return
        query = event.value.strip().lower()
        if query:
            scored: list[tuple[float, Entry]] = []
            for title_l, entry in zip(self._titles_lower, self._entries):
                score = _search_score(query, title_l)
                if score >= FUZZY_CUTOFF:
                    scored.append((score, entry))
            scored.sort(key=lambda t: t[0], reverse=True)
            self._filtered = [entry for _, entry in scored]
        else:
            self._filtered = None
        self.page = 0
        self.selected_idx = -1
        self._render_page()

    # ── Rendering ──

    def _render_page(self) -> None:
        self._gen += 1
        container = self.query_one("#entries-list", VerticalScroll)
        container.remove_children()

        page_entries = self._page_entries
        if not page_entries and self._filtered is not None:
            self._update_indicator()
            return

        gen = self._gen
        cards = [
            EntryCard(entry, id=f"card-{gen}-{i}")
            for i, entry in enumerate(page_entries)
        ]
        container.mount_all(cards)
        self._highlight_selected()
        self._update_indicator()

    def _update_indicator(self) -> None:
        indicator = self.query_one("#page-indicator", Static)
        total = len(self._active_entries)
        if self._filtered is not None:
            if total == 0:
                indicator.update(" No results")
            else:
                indicator.update(
                    f" Page {self.page + 1}/{self._total_pages}"
                    f"  ({total} results)"
                )
        else:
            indicator.update(
                f" Page {self.page + 1}/{self._total_pages}"
                f"  ({total} entries)"
            )

    # ── Selection / navigation ──

    def _highlight_selected(self) -> None:
        cards = list(self.query(EntryCard))
        for i, card in enumerate(cards):
            card.highlighted = i == self.selected_idx
        if cards and 0 <= self.selected_idx < len(cards):
            cards[self.selected_idx].scroll_visible()

    def action_next_page(self) -> None:
        if self.page < self._total_pages - 1:
            self.page += 1
            self.selected_idx = -1
            self._render_page()

    def action_prev_page(self) -> None:
        if self.page > 0:
            self.page -= 1
            self.selected_idx = -1
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
        if self.selected_idx < 0:
            return
        cards = list(self.query(EntryCard))
        if not cards:
            return
        idx = min(self.selected_idx, len(cards) - 1)
        entry = cards[idx].entry
        from src.applications.fulltui.screens.detail import DetailScreen

        self.app.push_screen(DetailScreen(entry, self.app.entry_svc))

    def action_back(self) -> None:
        """Clear search first; if already clear, go home."""
        inp = self.query_one("#search-input", Input)
        if inp.value:
            inp.value = ""
        else:
            self.app.switch_mode("home")

    def refresh_data(self) -> None:
        """Reload entries from the database."""
        self._load_entries()
