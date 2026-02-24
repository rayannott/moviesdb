from datetime import UTC, datetime, timedelta
from statistics import mean

from rich import box
from rich.align import Align
from rich.console import Console, RenderableType
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.prompt import Prompt
from rich.table import Table

from src.models.entry import Entry, EntryType
from src.obj.entry_group import EntryGroup
from src.obj.verbosity import is_verbose
from src.utils.utils import LOCAL_TZ, TAG_WATCH_AGAIN


def format_image_prefix(num_images: int) -> str:
    if num_images == 0:
        return ""
    if num_images == 1:
        return "[green][/]  "
    return f"[green] {num_images}[/] "


def get_rich_table(
    rows: list[list[str]],
    headers: list[str],
    *,
    title: str = "",
    justifiers: list[str] = [],
    styles: list[str | None] = [],
    center: bool = True,
) -> Table | Align:
    assert rows, "Rows must not be empty"
    assert not headers or (len(headers) == len(rows[0])), (
        f"Number of headers must match number of columns in rows: {len(headers)} != {len(rows[0])}"
    )
    assert all(len(row) == len(rows[0]) for row in rows), (
        "All rows must have the same number of columns"
    )

    if not justifiers:
        justifiers = ["right"] * len(headers)

    if not styles:
        styles = [None] * len(headers)

    table = Table(
        title=title,
        show_lines=True,
        show_header=bool(headers),
        style=styles[0] if len(styles) == 1 and styles[0] is not None else "white",
        box=box.ROUNDED,
    )

    for header, justifier, style in zip(headers, justifiers, styles):
        table.add_column(header, justify=justifier, style=style)  # type: ignore

    for row in rows:
        table.add_row(*row)

    return Align(table, align="center") if center else table


class Color:
    def __init__(self, red: int, green: int, blue: int):
        self.red = red
        self.green = green
        self.blue = blue

    def __repr__(self):
        return f"rgb({self.red},{self.green},{self.blue})"

    def interpolate(self, other: "Color", ratio: float):
        """Interpolate between two CustomColor objects."""
        red = round(self.red + ratio * (other.red - self.red))
        green = round(self.green + ratio * (other.green - self.green))
        blue = round(self.blue + ratio * (other.blue - self.blue))
        return Color(red, green, blue)


def format_rating(rating: float):
    min_color = Color(255, 0, 0)
    max_color = Color(0, 255, 0)

    min_value = 3.0
    max_value = 10.0

    if rating < min_value:
        color = min_color
    else:
        ratio = (rating - min_value) / (max_value - min_value)
        color = min_color.interpolate(max_color, ratio)
    extra = "!" if rating >= 9.0 else ""
    return f"[{color}]{rating:.2f}{extra}[/]"


def format_title(title: str, entry_type: EntryType) -> str:
    if entry_type == EntryType.SERIES:
        return f"[black on white]{title}[/]"
    return f"[bold]{title}[/]"


def format_movie_series(title: str, is_series: bool) -> str:
    return f"[black on white]{title}[/]" if is_series else title


def format_tag(tag: str) -> str:
    style = (
        "dodger_blue2"
        if tag == TAG_WATCH_AGAIN
        else ("bold cornflower_blue" if tag[0].isupper() else "bold blue")
    )
    return f"[{style}]󰓹 {tag}[/]"


def _entry_formatted_parts(entry: Entry) -> tuple[str, str, str, str, str]:
    def _fmt_date() -> str:
        if not entry.date:
            return ""
        now = datetime.now(UTC)
        time_utc = entry.date.time()
        dt_loc = entry.date.astimezone(LOCAL_TZ)
        time_loc = dt_loc.time()
        time_pretty = (
            time_loc.strftime(" at %H:%M") if time_utc != datetime.min.time() else ""
        )
        if entry.date == now.date():
            return f"today{time_pretty}"
        if entry.date == (now - timedelta(days=1)).date():
            return f"yesterday{time_pretty}"
        return entry.date.strftime("%d %b %Y") + time_pretty

    _title = format_image_prefix(len(entry.image_ids)) + format_title(
        entry.title, entry.type
    )
    _rating = format_rating(entry.rating)
    _date = _fmt_date()
    _tags = f"{' '.join(format_tag(t) for t in entry.tags)}" if entry.tags else ""
    _notes = f"{entry.notes}" if entry.notes and is_verbose else ""
    return _title, _rating, _date, _tags, _notes


def get_entries_table(
    entries: list[Entry] | tuple[Entry, ...],
    ids: list[int] | tuple[int, ...] = [],
    title: str = "",
    center: bool = True,
) -> Table | Align:
    take_ids = bool(ids)
    headers = (
        (["ID"] if take_ids else [])
        + [
            "Title",
            "Rating",
            "Date",
            "Tags",
        ]
        + (["Notes"] if is_verbose else [])
    )
    justifiers = (
        (["right"] if ids else [])
        + ["left", "middle", "right", "left"]
        + (["left"] if is_verbose else [])
    )
    rows = []
    if not ids:
        ids = list(range(1, len(entries) + 1))  # dummy ids
    for id_, entry in zip(ids, entries):
        _title, _rating, _date, _tags, _notes = _entry_formatted_parts(entry)
        rows.append(
            ([str(id_)] if take_ids else [])
            + [_title, _rating, _date, _tags]
            + ([_notes] if is_verbose else [])
        )
    return get_rich_table(
        rows, headers, title=title, justifiers=justifiers, center=center
    )


def get_groups_table(groups: list[EntryGroup], title: str = "") -> Table | Align:
    headers = ["Average Rating", "Title", "Last Watched", "Ratings"]
    justifiers = ["right", "left", "middle", "left"]
    rows = []
    for group in groups:
        from_str = group.watched_last.strftime("%d.%m.%Y") if group.watched_last else ""
        mean_str = format_rating(mean(group.ratings))
        ratings_str = ", ".join(map(format_rating, group.ratings))
        rows.append(
            [mean_str, format_title(group.title, group.type), from_str, ratings_str]
        )
    return get_rich_table(
        rows, headers, title=title, justifiers=justifiers, center=True
    )


def rinput(console: Console, prompt_text: str) -> str:
    return Prompt.get_input(console, prompt_text, False)


def format_entry(entry: Entry) -> str:
    _title, _rating, _date, _tags, _notes = _entry_formatted_parts(entry)
    # return f"[{self.rating:.2f}] {self.title}{type_str}{watched_date_str}{note_str}{tags_str}"
    _date_str = f" ({_date})" if _date else ""
    _tags_str = rf" \[{_tags}]" if _tags else ""
    _notes_str = f': "{_notes}" ' if is_verbose and _notes else ""
    return f"{_rating} {_title}{_date_str}{_tags_str}{_notes_str}"


def comparison(renderable1: RenderableType, renderable2: RenderableType) -> Table:
    table = Table(show_header=False, pad_edge=False, box=None, expand=True)
    table.add_column("1", ratio=1)
    table.add_column("2", ratio=1)
    table.add_row(renderable1, renderable2)
    return table


def get_pretty_progress() -> Progress:
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(bar_width=None),
        "[progress.percentage]{task.percentage:>3.0f}%",
        TimeElapsedColumn(),
        "->",
        TimeRemainingColumn(),
        expand=True,
        transient=True,
        refresh_per_second=30,
    )
