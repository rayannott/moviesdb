"""Bot-specific formatting utilities (plain text for Telegram)."""

from collections.abc import Callable
from typing import TypeVar

from src.models.entry import Entry
from src.obj.entry_group import EntryGroup

ObjectT = TypeVar("ObjectT")


def format_title(title: str, is_series: bool) -> str:
    return f"{title}{' (series)' if is_series else ''}"


def format_entry(entry: Entry, verbose: bool = False, with_oid: bool = False) -> str:
    note_str = f": {entry.notes}" if entry.notes and verbose else ""
    watched_date_str = f" ({entry.date.strftime('%d.%m.%Y')})" if entry.date else ""
    _num_images_str = (
        " {" + f"{len(entry.image_ids)} img" + "}" if entry.image_ids else ""
    )
    tags_str = f" [{' '.join(entry.tags)}]" if entry.tags else ""
    oid_part = "{" + entry.id[-4:] + "} " if with_oid and entry.id else ""
    title_fmt = format_title(entry.title, entry.is_series)
    return (
        f"{oid_part}[{entry.rating:.2f}] {title_fmt}"
        f"{watched_date_str}{_num_images_str}{note_str}{tags_str}"
    )


def list_many(
    objects: list[ObjectT],
    format_fn: Callable[..., str],
    first_n: bool,
    override_title: str | None = None,
    **kwargs: object,
) -> str:
    n = min(7, len(objects))
    _s = slice(None, n, None) if first_n else slice(-n, None, None)
    data = "\n".join(format_fn(obj, **kwargs) for obj in objects[_s])
    return (
        (f"{len(objects)} found:" if override_title is None else override_title)
        + "\n"
        + (
            (data + ("\n..." if len(objects) > n else ""))
            if first_n
            else (("...\n" if len(objects) > n else "") + data)
        )
    )


def list_many_entries(
    entries: list[Entry],
    verbose: bool = False,
    with_oid: bool = False,
    override_title: str | None = None,
) -> str:
    return list_many(
        entries,
        lambda entry: format_entry(entry, verbose, with_oid),
        first_n=False,
        override_title=override_title,
    )


def list_many_groups(
    groups: list[EntryGroup],
    override_title: str | None = None,
) -> str:
    return list_many(
        groups,
        EntryGroup.__str__,
        first_n=True,
        override_title=override_title,
    )
