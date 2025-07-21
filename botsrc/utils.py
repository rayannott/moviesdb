from collections.abc import Callable
from datetime import datetime
from typing import TypeVar

from git import Commit

from src.mongo import Mongo
from src.obj.entry import Entry
from src.obj.entry_group import EntryGroup
from src.obj.books_mode import Book
from src.paths import ALLOWED_USERS
from src.utils.utils import TAG_WATCH_AGAIN, RepoInfo

BOT_STARTED = datetime.now()


ALLOWED_USERS.parent.mkdir(exist_ok=True)


def select_entry_by_oid_part(oid_part: str, entries: list[Entry]) -> Entry | None:
    selected = [entry for entry in entries if oid_part in str(entry._id)]
    if len(selected) != 1:
        return None
    return selected[0]


def format_entry(entry: Entry, verbose: bool = False, with_oid: bool = False) -> str:
    note_str = f": {entry.notes}" if entry.notes and verbose else ""
    watched_date_str = f" ({entry.date.strftime('%d.%m.%Y')})" if entry.date else ""
    tags_str = f" [{' '.join(entry.tags)}]" if entry.tags else ""
    oid_part = "{" + str(entry._id)[-4:] + "} " if with_oid else ""
    return f"{oid_part}[{entry.rating:.2f}] {format_title(entry.title, entry.is_series)}{watched_date_str}{note_str}{tags_str}"


def format_book(book: Book, verbose: bool = False) -> str:
    """Format a book for display."""
    rating_str = f"[{book.rating:.2f}] " if book.rating is not None else ""
    author_str = f" by {book.author}" if book.author else ""
    pages_str = f" ({book.n_pages} pages)" if book.n_pages else ""
    body_str = f"\n{book.body}" if verbose and book.body else ""
    return f"{rating_str}{book.title}{author_str}{pages_str} (from {book.dt_read:%d.%m.%Y}){body_str}"


def format_title(title: str, is_series: bool) -> str:
    return f"{title}{' (series)' if is_series else ''}"


def process_watch_list_on_add_entry(entry: Entry) -> str:
    title_fmt = format_title(entry.title, entry.is_series)
    watch_list = Mongo.load_watch_list()
    if not watch_list.remove(entry.title, entry.is_series):
        return ""
    if not Mongo.delete_watchlist_entry(entry.title, entry.is_series):
        return f"Could not delete {title_fmt} from watch list."
    return f"Removed {title_fmt} from watch list."


def process_watch_again_tag_on_add_entry(entry: Entry) -> str:
    entries = Mongo.load_entries()
    entries_wa = [
        ent
        for ent in entries
        if TAG_WATCH_AGAIN in ent.tags
        and ent.title == entry.title
        and ent.type == entry.type
        and ent._id != entry._id
    ]
    if not entries_wa:
        return ""
    msg = "Removed the watch again tag from:"
    for ent in entries_wa:
        ent.tags.remove(TAG_WATCH_AGAIN)
        Mongo.update_entry(ent)
        msg += f"\n{format_entry(ent)}"
    return msg


ALLOW_GUEST_COMMANDS = {"list", "watch", "suggest", "find", "tag", "group", "books"}
HELP_GUEST_MESSAGE = """You can use the bot, but some commands may be restricted.
You can use the following commands (read-only):
    - list - to view the entries
    - find <title> - to find a title by name
    - watch - to view the watch list
    - suggest <message> - to suggest me a movie!
    - group [<title>] - group entries by title
    - tag [<tagname>] - to view tags stats or entries with the given tag
    - books - to view the books I've recently read"""

ME_CHAT_ID = 409474295


def report_repository_info() -> str:
    def _commit_to_str(commit: Commit) -> str:
        """Convert commit to string."""
        return f"""commit {commit.hexsha}
Author: {commit.author.name} <{commit.author.email}>
Date:   {commit.authored_datetime}
{commit.message}"""

    repo_info = RepoInfo()
    return f"""Bot started at {BOT_STARTED} on branch: {repo_info.on_branch}.
    - Last commit:
{_commit_to_str(repo_info.last_commit)}"""


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
