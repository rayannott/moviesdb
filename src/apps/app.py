from time import perf_counter as pc

from rich.console import Console

with Console().status("Loading dependencies..."):
    _t_dep_0 = pc()
    import json
    import logging
    import random
    from contextlib import nullcontext
    from datetime import datetime
    from functools import partial
    from itertools import batched, starmap
    from pathlib import Path
    from statistics import mean, stdev
    from typing import Any, Callable
    from zoneinfo import ZoneInfo

    from bson import ObjectId
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.progress import TaskID
    from rich.prompt import Prompt

    from setup_logging import setup_logging
    from src.apps.base import BaseApp
    from src.apps.book import BooksApp
    from src.apps.image import ImagesApp
    from src.apps.sqlapp import SqlApp
    from src.obj.ai import ChatBot
    from src.obj.entry import (
        Entry,
        MalformedEntryException,
        Type,
        build_tags,
        is_verbose,
    )
    from src.obj.entry_group import EntryGroup, groups_from_list_of_entries
    from src.obj.image import ImageManager
    from src.obj.omdb_response import get_by_title
    from src.obj.textual_apps import ChatBotApp, EntryFormApp
    from src.obj.watch_list import WatchList
    from src.parser import Flags, KeywordArgs, PositionalArgs
    from src.paths import LOCAL_DIR
    from src.utils.help_utils import get_rich_help
    from src.utils.plots import get_plot
    from src.utils.rich_utils import (
        format_entry,
        format_movie_series,
        format_rating,
        format_tag,
        format_title,
        get_entries_table,
        get_groups_table,
        get_pretty_progress,
        get_rich_table,
        rinput,
    )
    from src.utils.utils import (
        F_ALL,
        F_MOVIES,
        F_SERIES,
        TAG_WATCH_AGAIN,
        AccessRightsManager,
        RepoInfo,
        possible_match,
        replace_tag_alias,
    )

    DEP_LOADING_TIME = pc() - _t_dep_0

with Console().status("Connecting to MongoDB..."):
    _t_mongo_0 = pc()
    from src.mongo import Mongo

    MONGO_LOADING_TIME = pc() - _t_mongo_0


def identity(x: str):
    return x


def std(data: list[float] | list[int]) -> float:
    return stdev(data) if len(data) > 1 else 0.0


VALUE_MAP: dict[str, Callable[[str], Any]] = {
    "title": identity,
    "rating": Entry.parse_rating,
    "type": Entry.parse_type,
    "notes": identity,
    "date": Entry.parse_date,
}

logger = logging.getLogger(__name__)
setup_logging()


class App(BaseApp):
    @staticmethod
    def load_entries() -> list[Entry]:
        return Mongo.load_entries()

    @staticmethod
    def load_watch_list() -> WatchList:
        return Mongo.load_watch_list()

    @staticmethod
    def get_watch_table(watch_list_items: list[tuple[str, bool]]):
        n_cols = 3 if len(watch_list_items) >= 3 else len(watch_list_items)
        return get_rich_table(
            [
                list(titles) + [""] * (n_cols - len(titles))
                for titles in batched(
                    starmap(format_movie_series, watch_list_items), n_cols
                )
            ],
            title="Watch list",
            headers=[],
            styles=["cyan"],
        )

    @staticmethod
    def md(text: str) -> Markdown:
        return Markdown(text)

    def try_int(self, s) -> int | None:
        try:
            return int(s)
        except ValueError:
            self.cns.print(f" Not an integer: {s!r}", style="bold red")
        return None

    @property
    def entries(self) -> list[Entry]:
        return sorted(self.load_entries())

    @property
    def watch_list(self) -> WatchList:
        return self.load_watch_list()

    def __init__(self):
        self.running = True

        self.cns = Console()
        self.input = partial(rinput, self.cns)

        super().__init__(self.cns, input, prompt_str=">>>")  # keep builtin input

        self.chatbot = ChatBot(self.entries, Mongo)

        _t_repo_0 = pc()
        self.repo_info = RepoInfo()
        self.repo_info_loading_time = pc() - _t_repo_0

        logger.info(
            f"""init App; loading times:
dependencies={DEP_LOADING_TIME:.3f}s,
mongo={MONGO_LOADING_TIME:.3f}s,
repo={self.repo_info_loading_time:.3f}s;
{len(self.entries)} entries,
{len(self.watch_list)} watch list items""".replace("\n", " ")
        )

        self.recently_popped: list[Entry] = []

    def add_entry(self, entry: Entry):
        Mongo.add_entry(entry)

    def get_groups(self) -> list[EntryGroup]:
        """
        Group entries by title.
        Returns a list of EntryGroup objects, sorted by average rating descending.
        """
        return groups_from_list_of_entries(self.entries)

    def _find_exact_matches(
        self, title: str, ignore_case: bool = True
    ) -> list[tuple[int, Entry]]:
        def str_eq(s1: str, s2: str) -> bool:
            return s1.lower() == s2.lower() if ignore_case else s1 == s2

        return [(i, e) for i, e in enumerate(self.entries) if str_eq(title, e.title)]

    def _find_substring_matches(self, title: str) -> list[tuple[int, Entry]]:
        return [
            (i, e)
            for i, e in enumerate(self.entries)
            if title.lower() in e.title.lower() and title.lower() != e.title.lower()
        ]

    def _watch(self, title: str, is_series: bool):
        if (title, is_series) in self.watch_list:
            self.cns.print(
                f" {format_title(title, Type.SERIES if is_series else Type.MOVIE)} "
                "[bold red]is already in the watch list[/]",
            )
            return
        exact_matches = self._find_exact_matches(title)
        if exact_matches:
            entry = exact_matches[0][1]
            self.cns.print(
                f'[white]"{title}"[/] is already in the database  \n{format_entry(entry)}',
                style="bold yellow",
            )
            prompt = Prompt.ask(
                "What should we do with it\n"
                + "  [bold green]a[/]:  add to watch list anyway\n"
                + f"  [bold blue]t[/]: 󰓹 tag it with {format_tag(TAG_WATCH_AGAIN)}\n"
                + "  [bold red]n[/]:   nothing\n",
                choices=["a", "t", "n"],
                default="n",
            )
            if prompt == "t":
                entry.tags.add(TAG_WATCH_AGAIN)
                Mongo.update_entry(entry)
                self.cns.print(f"Done:\n{format_entry(entry)}")
                return
            elif prompt == "n":
                return
            return
        possible_title = possible_match(
            title, set(self.watch_list), score_threshold=0.7
        )
        if possible_title is not None and possible_title != title:
            update_title = Prompt.ask(
                f'[yellow] NOTE[/] entry with a similar title ("{possible_title}") exists. '
                f'Override "{title}" with "{possible_title}"?',
                choices=["y", "n"],
                default="n",
            )
            if update_title == "y":
                title = possible_title
        Mongo.add_watchlist_entry(title, is_series)
        self.cns.print(
            format_title(title, Type.SERIES if is_series else Type.MOVIE)
            + "[bold green] has been added to the watch list."
        )

    def _unwatch(self, title: str, is_series: bool):
        if not title:
            self.cns.print(" Empty title.", style="red")
            return
        title_fmtd = format_title(title, Type.SERIES if is_series else Type.MOVIE)
        if not self.watch_list.remove(title, is_series):
            self.error(f"{title_fmtd} is not in the watch list.")
            return
        if not Mongo.delete_watchlist_entry(title, is_series):
            self.error(f"There is no such watch list entry: {title_fmtd}.")
            return
        self.cns.print(
            title_fmtd + "[bold green] has been removed from the watch list."
        )

    def entry_by_idx(
        self, idx: int | str, *, suppress_errors: bool = False
    ) -> Entry | None:
        try:
            idx_ = int(idx)
            return self.entries[idx_]
        except (ValueError, IndexError):
            if not suppress_errors:
                self.error(f"Invalid index: {idx}.")
            return None

    def entry_by_idx_or_title(self, idx_title: str | int) -> Entry | None:
        """Get an entry by index or title.
        If a title matches multiple entries, return the most recent one."""
        by_id = self.entry_by_idx(idx_title, suppress_errors=True)
        if by_id:
            return by_id
        by_title = self._find_exact_matches(str(idx_title))
        if by_title:
            return by_title[-1][1]
        return None

    def header(self):
        branch = f"[violet] {self.repo_info.get_branch()}[/]"
        last_commit_from = f"[gold3]󰚰 {self.repo_info.get_last_commit_timestamp()}[/]"
        self.cns.rule(
            rf"[bold green]{len(self.entries)}[/] entries \[{branch} {last_commit_from}]"
        )

    def cmd_find(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """find <title>
        Find entries by the title substring."""
        title = " ".join(pos)
        if not title:
            self.error("Empty title.")
            return
        exact = self._find_exact_matches(title)
        sub = self._find_substring_matches(title)
        watch = self.watch_list.filter_items(
            key=lambda t, _: title.lower() in t.lower()
        )
        if exact:
            ids, matches = zip(*exact)
            self.cns.print(
                get_entries_table(
                    matches, ids, title=f"[bold green]{len(exact)}[/] exact matches"
                )
            )
        if sub:
            ids, matches = zip(*sub)
            self.cns.print(
                get_entries_table(
                    matches,
                    ids,
                    title=f"[bold yellow]{len(sub)}[/] possible matches",
                )
            )
        if watch:
            self.cns.print(self.get_watch_table(watch))

    def cmd_modify(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        if not pos:
            self.error("No index provided.")
            return
        idx = pos[0]
        if not (entry := self.entry_by_idx(idx)):
            return
        entry_app = EntryFormApp(
            title=entry.title,
            rating=str(entry.rating),
            is_series=entry.is_series,
            date=entry.date.strftime("%d.%m.%Y") if entry.date else "",
            notes=entry.notes + " " + " ".join(f"#{t}" for t in entry.tags),
            button_text="Modify",
            image_ids=entry.image_ids,
        )
        entry_app.run()
        if entry_app.entry is not None:
            if entry_app.entry == entry:
                self.warning("No changes made:")
                self.cns.print(format_entry(entry))
                return
            entry_app.entry._id = entry._id
            Mongo.update_entry(entry_app.entry)
            self.cns.print(
                f"[green]󰚰 Updated[/]\n - was: {format_entry(entry)}\n - now: {format_entry(entry_app.entry)}"
            )

    def cmd_tag(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """tag [<tagname>] [<index or title>] [--delete]
        Show all tags, list entries with a given tag, or add/remove a tag to/from an entry.
        If no arguments are specified, show all tags and their counts.
        If <tagname> is specified, show all entries with that tag.
        If <tagname> and <index or title> are specified, add the tag to the entry.
        If --delete is specified, remove the tag from the entry."""
        tags = build_tags(self.entries)
        if not pos:
            self.cns.print(
                get_rich_table(
                    [
                        [
                            format_tag(tag),
                            str(len(entries)),
                            f"{format_rating(mean(entry.rating for entry in entries))} ± {std([entry.rating for entry in entries]):.2f}",
                        ]
                        for tag, entries in sorted(
                            tags.items(), key=lambda x: len(x[1]), reverse=True
                        )
                    ],
                    ["Tag", "Count", "Rating"],
                    title="All tags",
                    justifiers=["left", "right", "center"],
                    styles=["cyan", "white", None],
                )
            )
            return
        tagname = replace_tag_alias(pos[0])
        if len(pos) == 1:
            if tagname not in tags:
                self.error(f"No such tag: {tagname}.")
                return
            entries_with_tag_table = get_entries_table(
                tags[tagname], title=f"Entries with {format_tag(tagname)}"
            )
            self.cns.print(entries_with_tag_table)
            return
        # movie specification by title (or index)
        title_or_idx = pos[1]
        entry = self.entry_by_idx_or_title(title_or_idx)
        if not entry:
            self.warning(f"No entry found matching idx or title: {title_or_idx!r}")
            return
        if {"d", "delete"} & flags:
            try:
                entry.tags.remove(tagname)
                self.cns.print(
                    f"{format_entry(entry)} [bold green]has been untagged from[/] {format_tag(tagname)}"
                )
                Mongo.update_entry(entry)
            except KeyError:
                self.cns.print(
                    f"{format_entry(entry)} [bold red]does not have the tag[/] {format_tag(tagname)}"
                )
            return
        if tagname in entry.tags:
            self.warning(f"The entry already has the tag {format_tag(tagname)}:")
            self.cns.print(format_entry(entry))
            return
        entry.tags.add(tagname)
        self.cns.print(
            f"{format_entry(entry)} [bold green]has been tagged with[/] {format_tag(tagname)}"
        )
        Mongo.update_entry(entry)

    def cmd_plot(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """plot
        Generate a bar plot of the ratings over time."""
        with self.cns.status("Generating..."):
            fig = get_plot(self.entries)
        fig.show()

    def cmd_note(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """note <text>
        Find entries by substring in notes."""
        note = " ".join(pos)
        if not note:
            self.error("Empty note")
            return
        matches = [
            (i, e)
            for i, e in enumerate(self.entries)
            if note.lower() in e.notes.lower()
        ]
        if matches:
            ids, entries = zip(*matches)
            self.cns.print(
                get_entries_table(
                    entries, ids, title=f"[bold yellow]{len(matches)}[/] matches"
                )
            )
        else:
            self.error("No matches found")

    def cmd_ai(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """ai [<prompt>] [--full | --reset | --memory | --forget <id> | --remember <text>]
        Ask the chatbot a question or open a TUI interface.
        If <prompt> is not given, open the chatbot TUI interface.
        If --full is specified, use the full chatGPT-4o model instead of the mini version.
        If --reset is specified, clear the conversation history.
        If --memory is specified, list the AI's saved memories about the user.
        If --forget <id> is specified, forget the memory item corresponding to the id.
        If --remember <text> is specified, add some information about the user manually."""
        if "reset" in flags:
            self.cns.print(
                f"Cleared {len(self.chatbot._conversation_history)} prompt-response pairs."
            )
            self.chatbot.reset()
            return
        if "memory" in flags:
            mem_items = Mongo.load_aimemory_items()
            if not mem_items:
                self.warning("No context about the user.")
                return
            for mi_id, mi_info in mem_items:
                self.cns.print(rf"[blue]\[{mi_id[-7:]}][/] [green]{mi_info}[/]")
            return
        if (mi_id_to_remove := kwargs.get("forget")) is not None:
            for mi_id, mi_info in Mongo.load_aimemory_items():
                if mi_id_to_remove in mi_id:
                    if not Mongo.delete_aimemory_item(ObjectId(mi_id)):
                        self.error(f"Failed to delete memory with {mi_id}.")
                        return
                    self.cns.print(f"󰺝 Deleted [blue]{mi_id}.")
                    break
            else:
                self.warning(f"No memory with {mi_id_to_remove}.")
            return
        if (to_remember := kwargs.get("remember")) is not None:
            oid = Mongo.add_aimemory_item(to_remember)
            self.cns.print(f"Inserted under [blue]{oid}.")
            return

        prompt = " ".join(pos).strip()
        if not prompt:
            chatbot = ChatBotApp(self.chatbot, "full" not in flags)
            chatbot.run()
            return
        t0 = pc()
        AI_STATUS_TEXT_OPTIONS = [
            "Beep Beep Boop Boop 󰚩",
            "Thinking hard ",
            "Asking ChatGPT 󱜸",
            "Thinking 🤔",
        ]
        with self.cns.status(f"[bold cyan]{random.choice(AI_STATUS_TEXT_OPTIONS)} ..."):
            result = self.chatbot.prompt(
                prompt,
                "full" not in flags,
            )
        t1 = pc()
        self.cns.print(
            Panel(
                self.md(result),
                title=f"[dim white]{t1 - t0:.2f}[/]s",
            )
        )

    def cmd_list(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """list [--series | --movies] [--gallery] [--n <n>] [--all]
        List last n entries (default is 5).
        If --all is specified, show all matched entries.
        If --gallery is specified, filter the entries that have attached images.
        If --series or --movies is specified, filter the entries by type."""
        if F_SERIES in flags and F_MOVIES in flags:
            self.error(f"Cannot specify both --{F_SERIES} and --{F_MOVIES} ")
            return
        int_str = kwargs.get("n", "5")
        if (n := self.try_int(int_str)) is None:
            return
        entries = self.entries
        if F_SERIES in flags:
            entries = [ent for ent in entries if ent.is_series]
        elif F_MOVIES in flags:
            entries = [ent for ent in entries if not ent.is_series]
        if "gallery" in flags:
            entries = [ent for ent in entries if ent.image_ids]
        _slice = slice(0, None, None) if F_ALL in flags else slice(-n, None, None)
        entries = entries[_slice]
        n = len(entries)
        self.cns.print(get_entries_table(entries, title=f"Last {n} entries"))

    def cmd_group(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """group [<title>] [--series | --movies] [--n <n>] [--all]
        Group entries by title (and type) and show the top n (default is 5).
        If <title> is not given, show the top n groups sorted by average rating.
        If --series or --movies is specified, filter the groups by type.
        If --all is specified, show all matched groups."""
        if F_SERIES in flags and F_MOVIES in flags:
            self.error(f"Cannot specify both --{F_SERIES} and --{F_MOVIES} ")
            return
        groups = self.get_groups()
        int_str = kwargs.get("n", "5")
        if (n := self.try_int(int_str)) is None:
            return
        if F_SERIES in flags:
            groups = [g for g in groups if g.type == Type.SERIES]
        elif F_MOVIES in flags:
            groups = [g for g in groups if g.type == Type.MOVIE]
        if title := " ".join(pos):
            groups = [g for g in groups if title.lower() in g.title.lower()]
        _title = f"Top {n} groups" + (f' with "{title}"' if title else "")
        _slice = slice(0, None, None) if F_ALL in flags else slice(0, n, None)
        if not groups[_slice]:
            self.error("No matches found")
            return
        self.cns.print(get_groups_table(groups[_slice], title=_title))

    def cmd_watch(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """watch [<title>] [--delete | --random]
        Show the watch list.
        If <title> is given, add it to the watch list.
        If --delete is specified, remove the title from the watch list.
        Without a title, if --random is specified, show a random title from the watch list.
        If <title> ends with a '+', it is considered a series."""
        title = " ".join(pos)
        if not flags and not title:
            if not self.watch_list:
                self.warning("Watch list is empty")
                return
            self.cns.print(self.get_watch_table(self.watch_list.items()))
            return
        if {"r", "random"} & flags:
            self.cns.print(format_movie_series(*random.choice(self.watch_list.items())))
            return
        if {"d", "delete"} & flags:
            self._unwatch(title.rstrip("+"), title.endswith("+"))
        else:
            self._watch(title.rstrip("+"), title.endswith("+"))

    def cmd_stats(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """stats [--dev]
        Show some statistics about the entries.
        If --dev is specified, show app stats (loading times, last commit info, etc.)."""
        # TODO: make pretty
        self.cns.print(f"Total entries:\n  {len(self.entries)}")
        movies = [e.rating for e in self.entries if not e.is_series]
        series = [e.rating for e in self.entries if e.is_series]
        avg_movies = mean(movies)
        avg_series = mean(series)
        stdev_movies = std(movies)
        stdev_series = std(series)
        self.cns.print(
            f"Averages:\n  - movies: {format_rating(avg_movies)} ± {stdev_movies:.3f} "
            f"(n={len(movies)})\n  - series: {format_rating(avg_series)} ± {stdev_series:.3f} (n={len(series)})"
        )
        groups = self.get_groups()
        watched_more_than_once = [g for g in groups if len(g.ratings) > 1]
        watched_times = [len(g.ratings) for g in groups]
        watched_times_mean = mean(watched_times)
        watched_times_stdev = std(watched_times)
        self.cns.print(
            f"There are {len(groups)} unique entries; {len(watched_more_than_once)} of them have been "
            f"watched more than once ({watched_times_mean:.2f} ± {watched_times_stdev:.2f} times on average).\n"
            f"There are {len(self.watch_list)} items in the watch list ({len(self.watch_list.movies)} movies, {len(self.watch_list.series)} series)."
        )

        if "dev" not in flags:
            return

        def format_commit(commit):
            if commit is None:
                return "[red]No info[/]"
            return (
                f"[bold cyan]{commit.hexsha[:8]}[/] "
                f"[dim]<{commit.author.name} <{commit.author.email}>[/] "
                f"[green]{commit.committed_datetime.strftime('%Y-%m-%d %H:%M:%S')}[/]\n  "
                f"{commit.message}"
            )

        self.cns.rule("Dev stats", style="bold magenta")
        self.cns.print(
            f"[magenta]Resolved dependencies in[/] {DEP_LOADING_TIME:.3f} sec\n"
            f"[magenta]Connected to MongoDB in[/] {MONGO_LOADING_TIME:.3f} sec\n"
            f"[magenta]Loaded repo info in[/] {self.repo_info_loading_time:.3f} sec\n\n"
            f"[magenta]Last commit:[/]\n"
            f"  {format_commit(self.repo_info.get_last_commit())}"
        )

    def cmd_help(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """help [<command>]
        Show help for the given command.
        If no argument is given, show for all.
        Note: 'help <cmd>' is equivalent to '<cmd> --help'."""
        query = pos[0] if pos else None
        self.cns.print(get_rich_help(query, self.help_messages))

    def cmd_get(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """get <index> [--verbose]
        Get entry by index.
        If --verbose is specified, show all details.
        E.g. 'get -1 --verbose' will show the last entry with all details."""
        if not pos:
            self.error("No index provided.")
            return
        idx = pos[0]
        if (entry := self.entry_by_idx(idx)) is None:
            return
        _f = "v" if {"v", "verbose"} & flags else ""
        self.cns.print(f"#{idx} {entry:{_f}}")

    def _process_watch_again_tag_on_add(self, for_entry: Entry):
        _same_title_with_watch_again: list[Entry] = []
        _same_title_num = 0
        for e in self.entries:
            if e.title != for_entry.title or e.type != for_entry.type:
                continue
            _same_title_num += 1
            if TAG_WATCH_AGAIN in e.tags:
                _same_title_with_watch_again.append(e)
        if not _same_title_with_watch_again:
            return
        for e in _same_title_with_watch_again:
            e.tags.remove(TAG_WATCH_AGAIN)
            Mongo.update_entry(e)
            self.cns.print(
                f"[green]󰺝 Removed tag {format_tag(TAG_WATCH_AGAIN)} from[/]\n{format_entry(e)}"
            )
        resp = Prompt.ask(
            f"Do you want to add the {format_tag(TAG_WATCH_AGAIN)} to this entry?",
            choices=["y", "n"],
            default="n",
        )
        if resp == "y":
            for_entry.tags.add(TAG_WATCH_AGAIN)

    def cmd_add(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """add [<title>] [--tui]
        Start adding a new entry.
        If the title is not given or --tui is specified, will open a text-based user interface to add the entry.
        Will ask for [bold blue]rating[/]: floating point number r, 0 <= r <= 10,
        [bold blue]type[/]: "series" or "movie" or nothing (default="movie"),
        [bold blue]date[/]: date of format dd.mm.yyyy or "now" or nothing (default=None),
        [bold blue]notes[/]: anything or nothing (default="")].
        If the title is given, will try to find an entry with the same title in the database and
        will ask to override it if it exists."""
        title = " ".join(pos)
        if "tui" in flags or not title:
            entry_app = EntryFormApp(button_text="Add", title=title)
            entry_app.run()
            if entry_app.entry is not None:
                self._try_add_entry(entry_app.entry)
            return
        if not title:
            self.error("Empty title.")
            return
        possible_title_entries = possible_match(
            title, {e.title for e in self.entries}, score_threshold=0.65
        )
        possible_title_in_watch_list = possible_match(
            title, set(self.watch_list), score_threshold=0.65
        )
        possible_title = possible_title_entries or possible_title_in_watch_list
        if (
            possible_title is not None
            and possible_title != title
            and title not in self.watch_list
        ):
            update_title = Prompt.ask(
                f'[bold blue] NOTE: entry with a similar title ("{possible_title}") exists. '
                f'Override "{title}" with "{possible_title}"?',
                choices=["y", "n"],
                default="n",
            )
            if update_title == "y":
                title = possible_title
        entries = self._find_exact_matches(title, ignore_case=False)
        if entries:
            self.cns.print(
                f" NOTE: entry with this exact title already exists {len(entries)} times",
                style="bold blue",
            )
        if title in self.watch_list:
            self.cns.print(
                " NOTE: this entry is in your watching list; it will be removed "
                + "from the list if you add it to the database (title and type must match).",
                style="bold blue",
            )
        try:
            rating = Entry.parse_rating(self.input("[bold cyan]rating: "))
            type = Entry.parse_type(
                Prompt.ask(
                    "[bold cyan]type",
                    choices=["movie", "series"],
                    default="movie"
                    if not self.watch_list.get(title, False)
                    else "series",
                ).lower()
            )
            notes = self.input("[bold cyan]notes: ")
            when = Entry.parse_date(
                self.input(r"[bold cyan]date [magenta]\[%d.%m.%Y/now/-][/] (-): ")
            )
        except MalformedEntryException as e:
            self.error(str(e))
            return
        except KeyboardInterrupt:
            self.cns.print("Cancelled", style="yellow")
            return
        entry = Entry(None, title, rating, when, type, notes)
        self._try_add_entry(entry)

    def cmd_images(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """images ...
        Manage images in the database.
        """
        images_app = ImagesApp(self, self.cns, self.input)
        images_app.run()

    def _try_add_entry(self, entry: Entry):
        self._process_watch_again_tag_on_add(entry)
        self.add_entry(entry)
        self.cns.print(f"[green] Added [/]\n{format_entry(entry)}")
        if not self.watch_list.remove(entry.title, entry.type == Type.SERIES):
            return
        if not Mongo.delete_watchlist_entry(entry.title, entry.type == Type.SERIES):
            self.error(
                f"Failed to remove {format_title(entry.title, entry.type)} from the watch list."
            )
            return
        self.cns.print(
            "[green]󰺝 Removed from watch list[/]: "
            + format_title(entry.title, entry.type)
        )

    def cmd_random(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """random [<n>] [--tag <tag>]
        Sample n random entries (default=1).
        If a tag is specified, show only those entries having the tag."""
        to_choose_from = (
            [e for e in self.entries if replace_tag_alias(tag) in e.tags]
            if (tag := kwargs.get("tag"))
            else self.entries
        )
        if not to_choose_from:
            extra = f" with tag {format_tag(tag)}" if tag else ""
            self.error(f"No entries found{extra}.")
            return
        if len(pos) == 1:
            if (n := self.try_int(pos[0])) is None:
                return
        else:
            n = 1
        n = min(len(to_choose_from), n)
        entries = random.sample(to_choose_from, k=n)
        for entry in entries:
            self.cns.print(format_entry(entry))

    def cmd_db(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """db <title>
        Get movie data from the online database (OMDb)."""
        title = " ".join(pos)
        if not title:
            self.error("Empty title.")
            return
        with self.cns.status("[bold cyan]󰇧 Requesting an Online Database..."):
            resp = get_by_title(title)
        if not resp:
            self.cns.print(" No response", style="red")
            return
        self.cns.print(resp.rich())

    def cmd_pop(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """pop [<index>] [--undo]
        Remove an entry by index from the database (this is reversible).
        If --undo is specified (and no index is given), restore the last popped entry."""
        if "undo" in flags:
            if not self.recently_popped:
                self.warning("No recently popped entries.")
                return
            self.cns.print(
                f"Found {len(self.recently_popped)} recently popped entries."
            )
            to_restore = self.recently_popped.pop()
            Mongo.add_entry(to_restore)
            self.cns.print(f"Restored:\n{format_entry(to_restore)}")
            return
        if not pos:
            self.error("No index provided.")
            return
        idx = pos[0]
        if not (popped_entry := self.entry_by_idx(idx)):
            return
        assert popped_entry._id
        if not Mongo.delete_entry(popped_entry._id):
            self.error(f"{format_entry(popped_entry)} was not in the database.")
            return
        self.cns.print(f"󰺝 Removed\n{format_entry(popped_entry)}")
        self.recently_popped.append(popped_entry)

    def cmd_export(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """export [--silent] [--full]
        Export the entries (movies and series) and the watch list to ./export-local/{db|watch_list}.json.
        If --silent is specified, do not print any messages.
        If --full is specified, also export: books, images."""

        def _print(what: str):
            if "silent" not in flags:
                self.cns.print(what)

        def _status(msg: str):
            return self.cns.status(msg) if "silent" not in flags else nullcontext()

        def _dump_export_meta(what: dict[str, float], with_images: bool):
            with open(LOCAL_DIR / "_meta.json", "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "now": datetime.now(tz=ZoneInfo("Europe/Berlin")).isoformat(),
                        "with_images": with_images,
                        "exported_in_sec": what,
                    },
                    f,
                    indent=2,
                )
                _print(f"Export completed in {sum(what.values()):.2f} seconds.")

        _time_took_to_export: dict[str, float] = {}

        _t0 = pc()

        LOCAL_DIR.mkdir(exist_ok=True)
        dbfile = LOCAL_DIR / "db.json"
        with dbfile.open("w", encoding="utf-8") as f:
            json.dump(
                [entry.as_dict() for entry in self.entries],
                f,
                indent=2,
                ensure_ascii=False,
            )
            _print(f"Exported {len(self.entries)} entries to {dbfile.absolute()}.")
        _t1 = pc()
        _time_took_to_export["entries"] = _t1 - _t0

        wlfile = LOCAL_DIR / "watch_list.json"
        with wlfile.open("w", encoding="utf-8") as f:
            json.dump(self.watch_list.items(), f, indent=2, ensure_ascii=False)
            _print(
                f"Exported {len(self.watch_list)} watch list entries to {wlfile.absolute()}."
            )
        _t2 = pc()
        _time_took_to_export["watch_list"] = _t2 - _t1

        if "full" not in flags:
            _dump_export_meta(_time_took_to_export, with_images=False)
            return

        # books
        _t3 = pc()
        with _status("[bold cyan] Exporting books..."):

            books_file = LOCAL_DIR / "books.json"
            books_json = [
                book.to_row()
                for book in sorted(
                    BooksApp.get_books(BooksApp.get_client()),
                    key=lambda b: b.dt_read,
                )
            ]
        with books_file.open("w", encoding="utf-8") as f:
            json.dump(books_json, f, indent=2, ensure_ascii=False)
            _print(f"Exported {len(books_json)} books to {books_file.absolute()}.")
        _t4 = pc()
        _time_took_to_export["books"] = _t4 - _t3

        # images
        _t5 = pc()

        with _status("[bold cyan] Loading images..."):
            image_manager = ImageManager(self.entries)
            _num_images = len(image_manager._get_s3_images_bare())
            _print(f"Found {_num_images} images in the database.")
        _ids_to_tags = {}
        _ids_to_tags = image_manager.load_tags_pretty(self.cns)
        imgs = image_manager.get_images(with_tags=_ids_to_tags)
        images_subdir = LOCAL_DIR / "images"
        images_subdir.mkdir(exist_ok=True)
        img_meta_file = images_subdir / "meta.json"
        with img_meta_file.open("w", encoding="utf-8") as f:
            json.dump([img.to_dict() for img in imgs], f, indent=2)
            _print(
                f"Exported the metadata of {len(imgs)} images to {img_meta_file.absolute()}."
            )

        with (images_progress := get_pretty_progress()):
            task = images_progress.add_task("Downloading images...", total=len(imgs))
            for img in imgs:
                image_manager._download_image_to(
                    img.s3_id, images_subdir / Path(img.s3_id).name
                )
                images_progress.update(task, advance=1)
        images_dir_size = sum(f.stat().st_size for f in images_subdir.iterdir())
        _print(
            f"Exported {len(imgs)} images to {images_subdir.absolute()} (total size: {images_dir_size * 2**-20:.3f} MB)"
        )
        _t6 = pc()
        _time_took_to_export["images"] = _t6 - _t5
        _dump_export_meta(_time_took_to_export, with_images=True)

    def cmd_guest(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
    ):
        """guest [--add <name>] [--remove <name>]
        Manage the guest list.
        add: add a name to the guest list.
        remove: remove a name from the guest list.
        If no arguments are given, show the guest list."""
        am = AccessRightsManager()
        if (name := kwargs.get("add")) is not None:
            am.add(name)
            self.cns.print(f"{name} added to the guests list", style="bold green")
        elif (name := kwargs.get("remove")) is not None:
            is_ok = am.remove(name)
            if is_ok:
                self.cns.print(
                    f"{name} removed from the guests list", style="bold green"
                )
            else:
                self.error(f"{name} was not in the guest list")
        else:
            self.cns.print("Guests: " + ", ".join(am.guests))

    def cmd_sql(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """sql
        Start the SQL-like query mode."""
        sql_mode = SqlApp(self.entries, self.cns, self.input)
        sql_mode.run()

    def cmd_books(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """books
        Start the books subapp."""
        books_mode = BooksApp(self.cns, self.input)
        books_mode.run()

    def cmd_game(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """game
        Start the guessing game subapp."""
        from src.obj.game import GuessingGame

        game = GuessingGame(self.get_groups(), self.cns, self.input)
        game.run()

    def cmd_verbose(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """verbose
        Toggle verbose mode.
        In verbose mode, the entries' notes are shown as well."""
        is_verbose.toggle()
        self.cns.print(
            f"Verbose mode {'on  ' if is_verbose else 'off  '}",
            style=f"bold {'green' if is_verbose else 'red'}",
        )

    def cmd_exit(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """exit
        Exit the application."""
        self.running = False

    def cmd_debug(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        raise NotImplementedError("Debug command not implemented")

    def pre_run(self):
        """Prepare the application to run."""
        super().pre_run()
        self.cmd_export([], {}, {"silent"})
