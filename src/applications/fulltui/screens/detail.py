"""Detail screen -- full-screen modal view of a single entry."""

from rich.text import Text
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Static

from src.applications.fulltui.widgets.entry_card import _fmt_date_short, _rating_color
from src.models.entry import Entry, EntryType
from src.services.entry_service import EntryService


class DetailScreen(ModalScreen):
    """Full-screen modal showing a single entry with related entries."""

    BINDINGS = [
        Binding("escape", "dismiss", "Close"),
    ]

    def __init__(self, entry: Entry, entry_service: EntryService, **kwargs) -> None:  # type: ignore[override]
        super().__init__(**kwargs)
        self._entry = entry
        self._entry_svc = entry_service

    def compose(self) -> ComposeResult:
        with Vertical(id="detail-container"):
            yield VerticalScroll(id="detail-content")

    def on_mount(self) -> None:
        content = self.query_one("#detail-content", VerticalScroll)

        e = self._entry
        color = _rating_color(e.rating)
        bang = "!" if e.rating >= 9.0 else ""
        type_label = "Series" if e.type == EntryType.SERIES else "Movie"
        date_str = _fmt_date_short(e)

        header = Text()
        header.append(f"\n  {e.title}", style="bold underline")
        header.append(f"  ({type_label})\n", style="dim")
        content.mount(Static(header, id="detail-title"))

        info = Text()
        info.append("  Rating: ", style="bold")
        info.append(f"{e.rating:.2f}{bang}", style=color)
        if date_str:
            info.append("\n  Date:   ", style="bold")
            info.append(date_str)
        if e.tags:
            info.append("\n  Tags:   ", style="bold")
            info.append(" ".join(f"#{t}" for t in sorted(e.tags)), style="blue")
        content.mount(Static(info, id="detail-info"))

        if e.notes:
            notes_text = Text()
            notes_text.append("\n  Notes\n", style="bold underline")
            notes_text.append(f"  {e.notes}\n")
            content.mount(Static(notes_text, id="detail-notes"))

        related = self._entry_svc.find_exact_matches(e.title)
        others = [(idx, r) for idx, r in related if r.id != e.id]
        if others:
            rel_text = Text()
            rel_text.append(
                f"\n  Other entries with this title ({len(others)})\n",
                style="bold underline",
            )
            for _, other in others:
                other_color = _rating_color(other.rating)
                other_date = _fmt_date_short(other)
                rel_text.append("  ")
                rel_text.append(f"{other.rating:.2f}", style=other_color)
                rel_text.append(f"  {other.title}")
                if other_date:
                    rel_text.append(f"  {other_date}", style="dim")
                rel_text.append("\n")
            content.mount(Static(rel_text, id="detail-related"))
