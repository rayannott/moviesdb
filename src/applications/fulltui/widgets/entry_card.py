"""Compact widget representing a single database entry."""

from datetime import UTC, datetime, timedelta

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from src.models.entry import Entry, EntryType
from src.utils.utils import LOCAL_TZ


def _rating_color(rating: float) -> str:
    """Map rating 0-10 to a red-green color string."""
    min_val, max_val = 3.0, 10.0
    clamped = max(min_val, min(rating, max_val))
    ratio = (clamped - min_val) / (max_val - min_val)
    r = round(255 * (1 - ratio))
    g = round(255 * ratio)
    return f"rgb({r},{g},0)"


def _fmt_date_short(entry: Entry) -> str:
    if not entry.date:
        return ""
    now = datetime.now(UTC)
    if entry.date.date() == now.date():
        return "today"
    if entry.date.date() == (now - timedelta(days=1)).date():
        return "yesterday"
    dt_loc = entry.date.astimezone(LOCAL_TZ)
    return dt_loc.strftime("%d %b %Y")


class EntryCard(Widget, can_focus=True):
    """A single-line focusable card for an entry."""

    highlighted = reactive(False)

    def __init__(self, entry: Entry, **kwargs) -> None:  # type: ignore[override]
        super().__init__(**kwargs)
        self.entry = entry

    def render(self) -> Text:
        e = self.entry
        color = _rating_color(e.rating)
        bang = "!" if e.rating >= 9.0 else ""
        rating_str = f"{e.rating:.2f}{bang}"

        type_marker = " [S]" if e.type == EntryType.SERIES else ""
        date_str = _fmt_date_short(e)
        date_part = f"  {date_str}" if date_str else ""
        tags_part = ("  " + " ".join(f"#{t}" for t in sorted(e.tags))) if e.tags else ""

        line = Text()
        line.append(f" {rating_str} ", style=color)
        line.append(f" {e.title}{type_marker}", style="bold")
        line.append(date_part, style="dim")
        line.append(tags_part, style="blue")
        return line

    def watch_highlighted(self, value: bool) -> None:
        if value:
            self.add_class("selected")
        else:
            self.remove_class("selected")
