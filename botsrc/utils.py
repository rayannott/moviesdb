from datetime import datetime

from git import Repo, Commit
from telebot import TeleBot

from src.obj.entry import Entry
from src.utils.utils import TAG_WATCH_AGAIN
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
    watched_date_str = f" ({entry.date.strftime('%d.%m.%Y')})" if entry.date else ""
    tags_str = f" [{' '.join(entry.tags)}]" if entry.tags else ""
    oid_part = "{" + str(entry._id)[-4:] + "} " if with_oid else ""
    return f"{oid_part}[{entry.rating:.2f}] {format_title(entry.title, entry.is_series)}{watched_date_str}{note_str}{tags_str}"


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
    ]
    if not entries_wa:
        return ""
    msg = "Removed the watch again tag from:"
    for ent in entries_wa:
        ent.tags.remove(TAG_WATCH_AGAIN)
        Mongo.update_entry(ent)
        msg += f"\n{format_entry(ent)}"
    return msg


ALLOW_GUEST_COMMANDS = {"list", "watch", "suggest", "find", "tag"}
HELP_GUEST_MESSAGE = """You can use the bot, but some commands may be restricted.
You can use the following commands (read-only):
    - list - to view the entries
    - find <title> - to find a title by name
    - watch - to view the watch list
    - suggest - to suggest me a movie!
    - tag [<tagname>] - to view tags stats or entries with the given tag"""

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
