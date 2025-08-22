import itertools
import random

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import ScrollableContainer, Vertical
from textual.widgets import (
    Button,
    Input,
    Markdown,
    RadioButton,
    RadioSet,
    Static,
    TextArea,
)

from src.obj.ai import ChatBot
from src.obj.entry import Entry, MalformedEntryException
from src.utils.rich_utils import format_entry


class EntryFormApp(App):
    CSS_PATH = "entryform.tcss"
    BINDINGS = [("ctrl+r", "next_theme()", "cycle themes")]

    def __init__(
        self,
        title: str | str = "",
        rating: int | str = "",
        is_series: bool = False,
        date: str | str = "",
        notes: str | str = "",
        button_text: str = "Save",
        **kwargs,
    ):
        self._title = title
        self._rating = rating
        self._is_series = is_series
        self._date = date
        self._notes = notes
        self._button_text = button_text
        self._other_entry_kwargs = kwargs
        super().__init__()
        self._themes = list(
            self.app.available_themes.keys()
            - {"textual-light", "solarized-light", "catppuccin-latte"}
        )
        random.shuffle(self._themes)
        self._themes_it = itertools.cycle(self._themes)
        self.action_next_theme()
        self.entry: Entry | None = None

    def action_next_theme(self) -> None:
        self.app.theme = next(self._themes_it)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Input(value=self._title, placeholder="Enter title", id="title")
            yield Input(
                value=str(self._rating),
                placeholder="Enter rating",
                type="number",
                id="rating",
            )
            with RadioSet(id="type"):
                yield RadioButton("movie", value=not self._is_series)
                yield RadioButton("series", value=self._is_series)
            yield Input(
                value=self._date, placeholder="Enter date (%d.%m.%Y/today/-)", id="date"
            )
            yield TextArea(text=self._notes, id="notes")
            yield Button(self._button_text, variant="primary", id="save")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "save":
            if self.parse():
                self.exit()

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        self._is_series = event.radio_set.pressed_index == 1

    def on_input_changed(self, event: Input.Changed) -> None:
        """Triggered whenever the input value changes."""
        input_id = event.input.id
        value = event.value.strip()

        if input_id == "rating":
            is_valid = self._validate_rating(value)
        elif input_id == "date":
            is_valid = self._validate_date(value)
        elif input_id == "title":
            is_valid = bool(value)
        else:
            is_valid = True

        if is_valid:
            event.input.remove_class("invalid")
        else:
            event.input.add_class("invalid")

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

    def parse(self) -> bool:
        title = self.query_one("#title", Input).value.strip()
        rating_str = self.query_one("#rating", Input).value.strip()
        media_type = "SERIES" if self._is_series else "MOVIE"
        date = self.query_one("#date", Input).value
        notes = self.query_one("#notes", TextArea).text

        try:
            if not title:
                raise MalformedEntryException("Empty title")
            rating = Entry.parse_rating(rating_str)
            date = Entry.parse_date(date)
            type = Entry.parse_type(media_type)
        except MalformedEntryException as e:
            self.notify(f" {e}", severity="error")
            return False
        else:
            self.entry = Entry(
                None,
                title,
                rating,
                date,
                type,
                notes,
                **self._other_entry_kwargs,
            )
            self.notify(f"Ok:\n{format_entry(self.entry)}.\n Ctrl+Q to exit.")
            return True


class GameApp(App): ...  # TODO implement


class SqlModeApp(App): ...  # TODO implement


class EntriesTableApp(App):
    """Table to display entries in a TUI app."""

    # TODO implement


class ChatBotApp(App):
    CSS_PATH = "chatbot.tcss"

    def __init__(self, chatbot: ChatBot, is_mini: bool):
        self.chatbot = chatbot
        self.is_mini = is_mini
        super().__init__()
        if not is_mini:
            self.notify("Using a larger model (gpt-4o).", severity="warning")

    def compose(self) -> ComposeResult:
        yield ScrollableContainer(id="chat-history")
        yield Input(placeholder="Type your message...", id="input")

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        input = event.input
        message = input.value.strip()
        if not message:
            return
        self.add_user_message(message)
        self.set_timer(0.1, lambda: self.add_bot_response(message))
        input.clear()

    def add_user_message(self, message: str) -> None:
        chat_history = self.query_one("#chat-history")
        formatted = Text(message, style="white")
        chat_history.mount(Static(formatted, classes="user-message"))
        chat_history.scroll_end(animate=False)

    def add_bot_response(self, message: str) -> None:
        if message == "exit":
            self.exit()
            return
        chat_history = self.query_one("#chat-history")
        markdown_content = Markdown(self.generate_markdown_response(message))

        container = Vertical(markdown_content, classes="bot-message")

        chat_history.mount(container)
        chat_history.scroll_end(animate=True)

    def generate_markdown_response(self, message: str) -> str:
        return self.chatbot.prompt(message, is_mini=self.is_mini)
