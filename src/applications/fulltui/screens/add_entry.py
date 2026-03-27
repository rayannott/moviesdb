"""Add entry screen -- modal form for adding a new database entry."""

from __future__ import annotations

from typing import TYPE_CHECKING

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, RadioButton, RadioSet, Static, TextArea

from src.exceptions import MalformedEntryException
from src.models.entry import Entry

if TYPE_CHECKING:
    from src.applications.fulltui.app import FullTUIApp


class AddEntryScreen(ModalScreen[Entry | None]):
    """Modal form for adding a new entry. Returns the Entry or None."""

    app: "FullTUIApp"

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, **kwargs) -> None:  # type: ignore[override]
        super().__init__(**kwargs)
        self._is_series = False
        self._entries_by_title: dict[str, list[Entry]] = {}
        self._watchlist_titles_map: dict[str, str] = {}
        self._last_case_warned: str | None = None

    def compose(self) -> ComposeResult:
        with Vertical(id="add-entry-container"):
            yield Static("  Add Entry", id="add-entry-title")
            yield Input(placeholder="Title", id="ae-title")
            yield Static("", id="ae-title-status", classes="hidden")
            yield Input(placeholder="Rating (0-10)", type="number", id="ae-rating")
            with RadioSet(id="ae-type"):
                yield RadioButton("movie", value=True)
                yield RadioButton("series", value=False)
            yield Input(placeholder="Date (%d.%m.%Y / today / -)", id="ae-date")
            yield TextArea(id="ae-notes")
            yield Button("Add", variant="primary", id="ae-save")

    def on_mount(self) -> None:
        for e in self.app.entry_svc.get_entries():
            self._entries_by_title.setdefault(e.title.lower(), []).append(e)
        self._watchlist_titles_map = {
            t.lower(): t
            for t, _ in self.app.watchlist_svc.get_items()
        }
        self.query_one("#ae-title", Input).focus()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "ae-save":
            self._submit()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self._is_series = event.radio_set.pressed_index == 1

    def on_input_changed(self, event: Input.Changed) -> None:
        input_id = event.input.id
        value = event.value.strip()

        if input_id == "ae-rating":
            is_valid = self._validate_rating(value)
        elif input_id == "ae-date":
            is_valid = self._validate_date(value)
        elif input_id == "ae-title":
            is_valid = bool(value)
            self._update_title_status(value)
        else:
            is_valid = True

        if is_valid:
            event.input.remove_class("invalid")
        else:
            event.input.add_class("invalid")

    def _update_title_status(self, title: str) -> None:
        status = self.query_one("#ae-title-status", Static)
        title_lower = title.lower()

        if title_lower in self._entries_by_title:
            entries = self._entries_by_title[title_lower]
            existing_title = entries[0].title
            count = len(entries)
            times = "time" if count == 1 else "times"

            dates = [e.date for e in entries if e.date is not None]
            date_suffix = ""
            if dates:
                last_date = max(dates)
                date_suffix = f", last from {last_date.strftime('%d %b %Y')}"

            if title != existing_title:
                status.update(
                    f'[bold yellow]found as "{existing_title}" '
                    f"{count} {times}{date_suffix})[/]"
                )
                if title_lower != self._last_case_warned:
                    self._last_case_warned = title_lower
                    self.notify(
                        f'Existing title: "{existing_title}" - use exact spelling',
                        severity="warning",
                    )
            else:
                status.update(
                    f"[bold green]found {count} {times}{date_suffix}[/]"
                )
            status.remove_class("hidden")

        elif title_lower in self._watchlist_titles_map:
            existing_title = self._watchlist_titles_map[title_lower]
            if title != existing_title:
                status.update(
                    f'[bold yellow]in watchlist as "{existing_title}"[/]'
                )
                if title_lower != self._last_case_warned:
                    self._last_case_warned = title_lower
                    self.notify(
                        f'Watchlist title: "{existing_title}" - use exact spelling',
                        severity="warning",
                    )
            else:
                status.update("[bold blue]found in watchlist[/]")
            status.remove_class("hidden")
        else:
            status.update("")
            status.add_class("hidden")
            self._last_case_warned = None

    def _validate_rating(self, rating: str) -> bool:
        try:
            Entry.parse_rating(rating)
        except MalformedEntryException:
            return False
        return True

    def _validate_date(self, date: str) -> bool:
        try:
            Entry.parse_date(date)
        except MalformedEntryException:
            return False
        return True

    def _submit(self) -> None:
        title = self.query_one("#ae-title", Input).value.strip()
        rating_str = self.query_one("#ae-rating", Input).value.strip()
        media_type = "SERIES" if self._is_series else "MOVIE"
        date_str = self.query_one("#ae-date", Input).value
        notes = self.query_one("#ae-notes", TextArea).text

        try:
            if not title:
                raise MalformedEntryException("Empty title")
            rating = Entry.parse_rating(rating_str)
            date = Entry.parse_date(date_str)
            entry_type = Entry.parse_type(media_type)
        except MalformedEntryException as e:
            self.notify(str(e), severity="error")
            return

        entry = Entry(title=title, rating=rating, date=date, type=entry_type, notes=notes)
        self.app.entry_svc.add_entry(entry)
        self.app.entry_svc.remove_from_watchlist_on_add(entry)
        self.notify(f"Added: {entry.title} [{entry.rating:.2f}]")
        self.dismiss(entry)

    def action_cancel(self) -> None:
        self.dismiss(None)
