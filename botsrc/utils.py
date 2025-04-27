from datetime import datetime

from git import Repo, Commit
from telebot import TeleBot

from src.obj.entry import Entry, Type
from src.paths import ALLOWED_USERS
from src.mongo import Mongo


BOT_STARTED = datetime.now()


ALLOWED_USERS.parent.mkdir(exist_ok=True)


def select_entry_by_oid_part(oid_part: str, entries: list[Entry]) -> Entry | None:
    selected = [entry for entry in entries if oid_part in str(entry._id)]
    if len(selected) != 1:
        return None
    return selected[0]


def format_entry(entry: Entry, verbose: bool = False, with_oid: bool = False) -> str:
    note_str = f": {entry.notes}" if entry.notes and verbose else ""
    type_str = f" ({entry.type.name.lower()})" if entry.type != Type.MOVIE else ""
    watched_date_str = f" ({entry.date.strftime('%d.%m.%Y')})" if entry.date else ""
    tags_str = f" [{' '.join(entry.tags)}]" if entry.tags else ""
    oid_part = "{" + str(entry._id)[-4:] + "} " if with_oid else ""
    return f"{oid_part}[{entry.rating:.2f}] {entry.title}{type_str}{watched_date_str}{note_str}{tags_str}"


def process_watch_list_on_add_entry(entry: Entry) -> bool:
    watch_list = Mongo.load_watch_list()
    is_series = entry.type == Type.SERIES
    if watch_list.get(entry.title) is is_series:
        Mongo.delete_watchlist_entry(entry.title, is_series)
        return True
    return False


ALLOW_GUEST_COMMANDS = {"list", "watch", "suggest", "find", "tag"}
HELP_GUEST_MESSAGE = """You can use the bot, but some commands may be restricted.
You can use the following commands (read-only):
    - list: to view the entries
    - find <title>: to find a title by name
    - watch: to view the watch list
    - suggest: to suggest me a movie!
    - tag [<tagname>]: to view tags stats or entries with the given tag"""

ME_CHAT_ID = 409474295


class Report:
    """Class to generate report about the bot."""

    def __init__(self):
        # repository info
        self.repo = Repo(".")
        self.recent_commits = list(self.repo.iter_commits(max_count=5))
        self.on_branch = self.repo.active_branch.name

    @staticmethod
    def _commit_to_str(commit: Commit) -> str:
        """Convert commit to string."""
        return f"""commit {commit.hexsha}
Author: {commit.author.name} <{commit.author.email}>
Date:   {commit.authored_datetime}
{commit.message}"""

    def report_repository_info(self) -> str:
        return f"""Bot started at {BOT_STARTED} on branch: {self.on_branch}.
    - Last commit:
{self._commit_to_str(self.recent_commits[0])}"""


def list_many_entries(
    entries: list[Entry],
    verbose: bool,
    with_oid: bool,
    bot: TeleBot,
    override_title: str | None = None,
) -> str:
    # TODO: move to own module? also make return a response?
    n = min(7, len(entries))
    return (
        (f"{len(entries)} found:\n" if override_title is None else "")
        + ("...\n" if len(entries) > n else "")
        + "\n".join(
            format_entry(ent, verbose=verbose, with_oid=with_oid)
            for ent in entries[-n:]
        )
    )
