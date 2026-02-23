from collections.abc import Callable
from datetime import datetime
from typing import TypeVar


from src.models.entry import Entry
from src.obj.entry_group import EntryGroup
from src.paths import ALLOWED_USERS

BOT_STARTED = datetime.now()


ALLOWED_USERS.parent.mkdir(exist_ok=True)


def select_entry_by_oid_part(oid_part: str, entries: list[Entry]) -> Entry | None:
    selected = [entry for entry in entries if oid_part in entry.id]
    if len(selected) != 1:
        return None
    return selected[0]


def format_entry(entry: Entry, verbose: bool = False, with_oid: bool = False) -> str:
    note_str = f": {entry.notes}" if entry.notes and verbose else ""
    watched_date_str = f" ({entry.date.strftime('%d.%m.%Y')})" if entry.date else ""
    _num_images_str = (
        " {" + f"{len(entry.image_ids)} img" + "}" if entry.image_ids else ""
    )
    tags_str = f" [{' '.join(entry.tags)}]" if entry.tags else ""
    oid_part = "{" + entry.id[-4:] + "} " if with_oid else ""
    return f"{oid_part}[{entry.rating:.2f}] {format_title(entry.title, entry.is_series)}{watched_date_str}{_num_images_str}{note_str}{tags_str}"


def format_title(title: str, is_series: bool) -> str:
    return f"{title}{' (series)' if is_series else ''}"


ALLOW_GUEST_COMMANDS = {"list", "watch", "suggest", "find", "tag", "group"}
HELP_GUEST_MESSAGE = """You can use the bot, but some commands may be restricted.
You can use the following commands (read-only):
    - list - to view the entries
    - find <title> - to find a title by name
    - watch - to view the watch list
    - suggest <message> - to suggest me a movie!
    - group [<title>] - group entries by title
    - tag [<tagname>] - to view tags stats or entries with the given tag"""

ME_CHAT_ID = 409474295


ObjectT = TypeVar("ObjectT")


def list_many(
    objects: list[ObjectT],
    format_fn: Callable[[ObjectT], str],
    first_n: bool,
    override_title: str | None = None,
    **kwargs,
) -> str:
    # TODO: move to own module? also make return a response?
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
    verbose: bool,
    with_oid: bool,
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
