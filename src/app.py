from rich.console import Console

with Console().status("Loading dependencies..."):
    import os
    import random
    import json
    import time
    from collections import defaultdict
    from functools import partial
    from itertools import batched, starmap
    from statistics import mean, stdev
    from typing import Any, Callable

    import dotenv
    from rich.markdown import Markdown
    from rich.panel import Panel
    from rich.prompt import Prompt

    from pymongo.mongo_client import MongoClient
    from pymongo.server_api import ServerApi
    from pymongo.collection import Collection
    from bson import ObjectId

    from src.obj.ai import ChatBot
    from src.obj.entry import Entry, MalformedEntryException, Type, is_verbose
    from src.obj.entry_group import EntryGroup
    from src.obj.game import GuessingGame
    from src.obj.omdb_response import get_by_title
    from src.obj.sql_mode import SqlMode
    from src.obj.textual_apps import ChatBotApp, EntryFormApp
    from src.parser import Flags, KeywordArgs, ParsingError, PositionalArgs, parse
    from src.utils.plots import get_plot
    from src.paths import LOCAL_DIR
    from src.utils.rich_utils import (
        format_entry,
        format_movie_series,
        format_rating,
        format_tag,
        format_title,
        get_entries_table,
        get_groups_table,
        get_rich_table,
        rinput,
    )
    from src.utils.utils import possible_match

dotenv.load_dotenv()

F_SERIES = "series"
F_MOVIES = "movies"
F_ALL = "all"

TAG_WATCH_AGAIN = "watch-again"

MONGODB_PASSWORD = os.environ.get("MONGODB_PASSWORD")
assert MONGODB_PASSWORD is not None


with Console().status("Connecting to MongoDB..."):
    uri = f"mongodb+srv://rayannott:{MONGODB_PASSWORD}@moviesseries.7g8z1if.mongodb.net/?retryWrites=true&w=majority&appName=MoviesSeries"
    CLIENT = MongoClient(uri, server_api=ServerApi("1"))
    CLIENT.admin.command("ping")


# TODO: add types
def entries() -> Collection:
    return CLIENT.db.entries


def watchlist() -> Collection:
    return CLIENT.db.watchlist


def aimemory() -> Collection:
    return CLIENT.db.aimemory


def identity(x: str):
    return x


VALUE_MAP: dict[str, Callable[[str], Any]] = {
    "title": identity,
    "rating": Entry.parse_rating,
    "type": Entry.parse_type,
    "notes": identity,
    "date": Entry.parse_date,
}


class App:
    HELP_DATA: list[tuple[str, str]] = [
        ("help", "show help for all commands"),
        ("help <command>", "show help for a specific command"),
        ("exit", "quit the app"),
        ("find <word>", "find movie by title or substring of title (ignores case)"),
        ("note <word>", "find movie by substing in note (ignores case)"),
        ("pop <index>", "remove entry by index"),
        ("pop --undo", "unpop the most recently popped entry"),
        ("export", "export the entries and the watch list as json files"),
        (
            "list [--series|--movies, --all, --n=<number>]",
            "list last n entries (default is 5, --n=<number> to specify); --all to list all; --series or --movies to filter by type",
        ),
        (
            "group [--series|--movies, --all, --n=<number>]",
            "a quick overview of the top n (default is 5) entries by average rating; --series or --movies to filter by type; --all to show all matched entry groups",
        ),
        (
            r"group <title> \[arguments?]",
            "find groups by title substring; can use the same arguments as in group command",
        ),
        ("watch", "show the watch list"),
        ("watch <title>", "add title to the watch list"),
        ("watch <title> --delete", "remove title from the watch list"),
        ("watch --random", "show a random title from the watch list"),
        (
            "get <idx> [--verbose]",
            "get entry by index; --verbose to override verbosity and show all details",
        ),
        ("stats", "show some statistics about the entries"),
        (
            "add <title>",
            r'start adding a new entry; will ask for [bold blue]rating[/]: floating point number r, 0 <= r <= 10, \[[bold blue]type[/]: "series" or "movie" or nothing(default="movie"), '
            '[bold blue]date[/]: date of format dd.mm.yyyy or "now" or nothing(default=None), [bold blue]notes[/]: anything or nothing(default="")]',
        ),
        ("add [<title>] --tui", "add entry using a text-based user interface! 󱁖"),
        (
            "modify <index>",
            "modify entry by index using a text-based user interface! 󱁖",
        ),
        ("db <title>", "get movie data from the online database (OMDb)"),
        ("tag", "show all tags"),
        ("tag <tagname>", "show all entries with the tag"),
        ("tag <tagname> <index or title>", "add tag to entry by index or title"),
        (
            "tag <tagname> <index or title> --delete",
            "remove tag from entry by index or title",
        ),
        ("plot", "show a bar plot of the ratings over time"),
        (
            "random [<n>] [--tag <tag>]",
            "sample n random entries (default=1); if a tag is specified, show only those entries having the tag",
        ),
        ("game", "play a guessing game"),
        (
            "sql",
            "enter SQL mode: write SQLite queries for the in-memory database of entries",
        ),
        ("verbose", "toggle verbose mode"),
        ("cls", "clear the terminal"),
        (
            "ai <prompt> [--full]",
            "ask the chatGPT a question; --full to use chatGPT-4o instead of chatGPT-4o-mini",
        ),
        ("ai [--full]", "open the chatbot TUI interface"),
        ("ai --reset", "forget the conversation history"),
        ("ai --memory", "list the AI's saved memories about the user"),
        (
            "ai --forget <memory item id>",
            "forget the memory item corresponding to an id",
        ),
        (
            "ai --remember <memory item>",
            "add some information about the user manually",
        ),
    ]
    COMMANDS = {f[0].split()[0] for f in HELP_DATA}

    @staticmethod
    def load_entries_mongo() -> list[Entry]:
        data = entries().find()
        return [Entry.from_dict(entry) for entry in data]

    @staticmethod
    def load_watch_list_mongo() -> dict[str, bool]:
        data = watchlist().find()
        return {item["title"]: item["is_series"] for item in data}

    @staticmethod
    def build_tags(entries: list[Entry]):
        tags: defaultdict[str, list[Entry]] = defaultdict(list)
        for entry in entries:
            for tag in entry.tags:
                tags[tag].append(entry)
        return tags

    @staticmethod
    def get_watch_table(watch_list: dict[str, bool]):
        n_cols = 3 if len(watch_list) >= 3 else len(watch_list)
        return get_rich_table(
            [
                list(titles) + [""] * (n_cols - len(titles))
                for titles in batched(
                    starmap(format_movie_series, watch_list.items()), n_cols
                )
            ],
            title="Watch list",
            headers=[],
            styles=["cyan"],
        )

    def error(self, text: str):
        self.cns.print(f" {text}", style="bold red")

    def warning(self, text: str):
        self.cns.print(f" {text}", style="bold yellow")

    # def dump_entries(self):
    #     with DB_FILE.open("w", encoding="utf-8") as f:
    #         json.dump(
    #             [entry.as_dict() for entry in sorted(self.entries)],
    #             f,
    #             indent=2,
    #             ensure_ascii=False,
    #         )

    # def dump_watch_list(self):
    #     with WATCH_LIST_FILE.open("w", encoding="utf-8") as f:
    #         json.dump(self.watch_list, f, indent=2, ensure_ascii=False)

    @staticmethod
    def md(text: str) -> Markdown:
        return Markdown(text)

    def try_int(self, s) -> int | None:
        try:
            return int(s)
        except ValueError:
            self.cns.print(f" Not an integer: {s!r}", style="bold red")

    def __init__(self):
        self.running = True
        self._load_all()

        self.cns = Console()
        self.input = partial(rinput, self.cns)

        self.chatbot = ChatBot(self.entries, aimemory)

        self.command_methods: dict[
            str, Callable[[PositionalArgs, KeywordArgs, Flags], None]
        ] = {
            method_name[4:]: getattr(self, method_name)
            for method_name in dir(self)
            if method_name.startswith("cmd_")
        }

        self.recently_popped: list[Entry] = []

    def _load_all(self):
        self.entries = sorted(self.load_entries_mongo())
        self.watch_list = self.load_watch_list_mongo()

    def add_entry(self, entry: Entry):
        new_id = entries().insert_one(entry.as_dict()).inserted_id
        entry._id = new_id
        self.entries.append(entry)

    def get_groups(self) -> list[EntryGroup]:
        """
        Group entries by title.
        Returns a list of EntryGroup objects, sorted by average rating descending.
        """
        grouped = defaultdict(list)
        for entry in self.entries:
            grouped[entry.title].append(entry)
        return sorted(
            [EntryGroup.from_list_of_entries(entries) for entries in grouped.values()],
            key=lambda group: group.mean_rating,
            reverse=True,
        )

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

    def _watch(self, title_given: str):
        is_series = title_given.endswith("+")
        title = title_given.rstrip("+ ")
        if title in self.watch_list and self.watch_list[title] is is_series:
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
                entries().replace_one({"_id": entry._id}, entry.as_dict())
                self.cns.print(f"Done:\n{format_entry(entry)}")
                return
            elif prompt == "n":
                return
            return
        possible_title = possible_match(
            title, set(self.watch_list.keys()), score_threshold=0.7
        )
        if possible_title is not None:
            update_title = Prompt.ask(
                f'[yellow] NOTE[/] entry with a similar title ("{possible_title}") exists. '
                f'Override "{title}" with "{possible_title}"?',
                choices=["y", "n"],
                default="n",
            )
            if update_title == "y":
                title = possible_title
        self.watch_list[title] = is_series
        watchlist().insert_one({"title": title, "is_series": is_series})
        self.cns.print(
            format_title(title, Type.SERIES if is_series else Type.MOVIE)
            + "[bold green] has been added to the watch list."
        )

    def _unwatch(self, title_given: str):
        title = title_given.rstrip("+ ")
        if not title:
            self.cns.print(" Empty title.", style="red")
            return
        if title not in self.watch_list:
            self.warning(f"{title} is not in the watch list")
            return
        title_fmtd = format_title(
            title, Type.SERIES if self.watch_list[title] else Type.MOVIE
        )
        del self.watch_list[title]
        delete_res = watchlist().delete_one({"title": title})
        if delete_res.deleted_count == 0:
            self.error(f"{title_fmtd} was not in the database")
            return
        self.cns.print(
            title_fmtd + "[bold green] has been removed from the watch list."
        )

    def entry_by_idx(self, idx: int | str) -> Entry | None:
        try:
            idx_ = int(idx)
            return self.entries[idx_]
        except (ValueError, IndexError):
            self.error(f"Invalid index: {idx}.")
            return None

    def header(self):
        self.cns.rule(f"[bold green]{len(self.entries)}[/] entries")

    def cmd_find(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        title = " ".join(pos)
        if not title:
            self.error("Empty title.")
            return
        exact = self._find_exact_matches(title)
        sub = self._find_substring_matches(title)
        watch = {
            watch_title: _is_series
            for watch_title, _is_series in self.watch_list.items()
            if title.lower() in watch_title.lower()
        }
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
            is_series=entry.type == Type.SERIES,
            date=entry.date.strftime("%d.%m.%Y") if entry.date else "",
            notes=entry.notes + " " + " ".join(f"#{t}" for t in entry.tags),
            button_text="Modify",
        )
        entry_app.run()
        if entry_app.entry is not None:
            if entry_app.entry == entry:
                self.warning("No changes made:")
                self.cns.print(format_entry(entry))
                return
            entry_app.entry._id = entry._id
            self.entries[int(idx)] = entry_app.entry
            entries().replace_one({"_id": entry._id}, entry_app.entry.as_dict())
            self.cns.print(
                f"[green]󰚰 Updated[/]\n - was: {format_entry(entry)}\n - now: {format_entry(entry_app.entry)}"
            )

    def cmd_tag(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        tags = self.build_tags(self.entries)
        if not pos:
            self.cns.print(
                get_rich_table(
                    [
                        [format_tag(tag), str(len(entries))]
                        for tag, entries in sorted(
                            tags.items(), key=lambda x: len(x[1]), reverse=True
                        )
                    ],
                    ["Tag", "Count"],
                    title="All tags",
                    justifiers=["left", "right"],
                    styles=["cyan", "white"],
                )
            )
            return
        tagname = pos[0]
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
        exact_matches = self._find_exact_matches(title_or_idx)
        if exact_matches:
            entry = exact_matches[-1][1]
        else:
            if not (entry := self.entry_by_idx(title_or_idx)):
                return
        if {"d", "delete"} & flags:
            try:
                entry.tags.remove(tagname)
                self.cns.print(
                    f"{format_entry(entry)} [bold green]has been untagged from[/] {format_tag(tagname)}"
                )
                entries().replace_one({"_id": entry._id}, entry.as_dict())
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
        entries().replace_one({"_id": entry._id}, entry.as_dict())

    def cmd_plot(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        with self.cns.status("Generating..."):
            fig = get_plot(self.entries)
        fig.show()

    def cmd_note(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
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
            ids, matches = zip(*matches)
            self.cns.print(
                get_entries_table(
                    matches, ids, title=f"[bold yellow]{len(matches)}[/] matches"
                )
            )
        else:
            self.error("No matches found")

    def cmd_ai(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        if "reset" in flags:
            self.cns.print(
                f"Cleared {len(self.chatbot._conversation_history)} prompt-response pairs."
            )
            self.chatbot.reset()
            return
        if "memory" in flags:
            mem_items = self.chatbot.get_memory_items()
            if not mem_items:
                self.warning("No context about the user.")
                return
            for mi_id, mi_info in mem_items:
                self.cns.print(rf"[blue]\[{mi_id[-7:]}][/] [green]{mi_info}[/]")
            return
        if (mi_id_to_remove := kwargs.get("forget")) is not None:
            for mi_id, mi_info in self.chatbot.get_memory_items():
                if mi_id_to_remove in mi_id:
                    aimemory().delete_one({"_id": ObjectId(mi_id)})
                    self.cns.print(f"󰺝 Deleted [blue]{mi_id}.")
                    break
            else:
                self.warning(f"No memory with {mi_id_to_remove}.")
            return
        if (to_remember := kwargs.get("remember")) is not None:
            oid = self.chatbot.add_memory_item(to_remember)
            self.cns.print(f"Inserted under [blue]{oid}.")
            return

        prompt = " ".join(pos).strip()
        if not prompt:
            chatbot = ChatBotApp(self.chatbot, "full" not in flags)
            chatbot.run()
            return
        t0 = time.perf_counter()
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
        t1 = time.perf_counter()
        self.cns.print(
            Panel(
                self.md(result),
                title=f"[dim white]{t1 - t0:.2f}[/]s",
            )
        )

    def cmd_list(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        if F_SERIES in flags and F_MOVIES in flags:
            self.error(f"Cannot specify both --{F_SERIES} and --{F_MOVIES} ")
            return
        int_str = kwargs.get("n", "5")
        if (n := self.try_int(int_str)) is None:
            return
        entries = self.entries
        if F_SERIES in flags:
            entries = [ent for ent in entries if ent.type == Type.SERIES]
        elif F_MOVIES in flags:
            entries = [ent for ent in entries if ent.type == Type.MOVIE]
        _slice = slice(0, None, None) if F_ALL in flags else slice(-n, None, None)
        self.cns.print(get_entries_table(entries[_slice], title=f"Last {n} entries"))

    def cmd_group(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
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
        title = " ".join(pos)
        if not flags and not title:
            if not self.watch_list:
                self.warning("Watch list is empty")
                return
            self.cns.print(self.get_watch_table(self.watch_list))
            return
        if {"r", "random"} & flags:
            self.cns.print(
                format_movie_series(*random.choice(list(self.watch_list.items())))
            )
            return
        if {"d", "delete"} & flags:
            self._unwatch(title)
        else:
            self._watch(title)

    def cmd_stats(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        # TODO: make pretty
        self.cns.print(f"Total entries:\n  {len(self.entries)}")
        movies = [e.rating for e in self.entries if e.type == Type.MOVIE]
        series = [e.rating for e in self.entries if e.type == Type.SERIES]
        avg_movies = mean(movies)
        avg_series = mean(series)
        stdev_movies = stdev(movies)
        stdev_series = stdev(series)
        self.cns.print(
            f"Averages:\n  - movies: {format_rating(avg_movies)} ± {stdev_movies:.3f} (n={len(movies)})\n  - series: {format_rating(avg_series)} ± {stdev_series:.3f} (n={len(series)})"
        )
        groups = self.get_groups()
        watched_more_than_once = [g for g in groups if len(g.ratings) > 1]
        self.cns.print(
            f"There are {len(groups)} unique entries; {len(watched_more_than_once)} of them have been watched more than once."
        )

    def cmd_help(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        cmd = pos[0] if pos else ""
        if cmd:
            matches = [(c, d) for c, d in self.HELP_DATA if c.startswith(pos[0])]
        else:
            matches = self.HELP_DATA
        if not matches:
            self.error(f"No help found for {cmd!r}")
            maybe = possible_match(cmd, self.COMMANDS)
            if maybe:
                self.cns.print(f'Did you mean: "{maybe}"?')
            return
        else:
            cmd = matches[0][0].split()[0]
        self.cns.print(
            get_rich_table(
                list(map(list, matches)),
                ["Command", "Description"],
                title="Help" + (f' for "{cmd}"' if cmd else ""),
                justifiers=["left", "left"],
                styles=["cyan", "white"],
            )
        )

    def cmd_get(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        if not pos:
            self.error("No index provided")
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
            if e.title == for_entry.title:
                _same_title_num += 1
                if TAG_WATCH_AGAIN in e.tags:
                    _same_title_with_watch_again.append(e)
        if _same_title_with_watch_again:
            resp = Prompt.ask(
                f"[bold blue] NOTE: some entries ({len(_same_title_with_watch_again)}/{_same_title_num}) associated with "
                f"the newly added entry have the tag {format_tag(TAG_WATCH_AGAIN)}. "
                "Do you want to remove it (them)?",
                choices=["y", "n"],
                default="n",
            )
            if resp.lower() == "y":
                for e in _same_title_with_watch_again:
                    e.tags.remove(TAG_WATCH_AGAIN)
                    self.cns.print(
                        f"[green]󰺝 Removed tag {format_tag(TAG_WATCH_AGAIN)} from[/]\n{format_entry(e)}"
                    )

    def cmd_add(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
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
            title, set(self.watch_list.keys()), score_threshold=0.65
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

    def _try_add_entry(self, entry: Entry):
        self._process_watch_again_tag_on_add(entry)
        self.add_entry(entry)
        self.cns.print(f"[green] Added [/]\n{format_entry(entry)}")
        if entry.title in self.watch_list:
            if (entry.type == Type.SERIES) is self.watch_list[
                entry.title
            ] or Prompt.ask(
                "[bold blue] NOTE: Entry type does not match the watch list: "
                f"{entry.type} vs {'series' if self.watch_list[entry.title] else 'movie'}. "
                "The entry will not be removed from the watch list. "
                "Do you want to remove it anyway?",
                choices=["y", "n"],
                default="n",
            ) == "y":
                self._unwatch(entry.title)
        # self.dump_entries()

    def cmd_random(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        to_choose_from = (
            [e for e in self.entries if tag in e.tags]
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
        if "undo" in flags:
            if not self.recently_popped:
                self.warning("No recently popped entries.")
                return
            self.cns.print(
                f"Found {len(self.recently_popped)} recently popped entries."
            )
            to_restore = self.recently_popped.pop()
            new_id = entries().insert_one(to_restore.as_dict()).inserted_id
            to_restore._id = new_id
            self.entries.append(to_restore)
            self.cns.print(f"Restored:\n{format_entry(to_restore)}")
            return
        if not pos:
            self.error("No index provided.")
            return
        idx = pos[0]
        if not (entry := self.entry_by_idx(idx)):
            return
        popped_entry = self.entries.pop(int(idx))
        delete_res = entries().delete_one({"_id": popped_entry._id})
        if delete_res.deleted_count == 0:
            self.error(f"{format_entry(popped_entry)} was not in the database.")
            return
        self.cns.print(f"󰺝 Removed\n{format_entry(entry)}")
        self.recently_popped.append(popped_entry)

    def cmd_export(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        LOCAL_DIR.mkdir(exist_ok=True)
        dbfile = LOCAL_DIR / "db.json"
        with dbfile.open("w", encoding="utf-8") as f:
            json.dump(
                [entry.as_dict() for entry in sorted(self.entries)],
                f,
                indent=2,
                ensure_ascii=False,
            )
            self.cns.print(
                f"Exported {len(self.entries)} entries to {dbfile.absolute()}."
            )
        wlfile = LOCAL_DIR / "watch_list.json"
        with wlfile.open("w", encoding="utf-8") as f:
            json.dump(self.watch_list, f, indent=2, ensure_ascii=False)
            self.cns.print(
                f"Exported {len(self.watch_list)} watch list entries to {wlfile.absolute()}."
            )

    def cmd_sql(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        sql_mode = SqlMode(self.entries, self.cns, self.input)
        sql_mode.run()

    def cmd_game(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        game = GuessingGame(self.get_groups(), self.cns, self.input)
        game.run()

    def cmd_verbose(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        is_verbose.toggle()
        self.cns.print(
            f"Verbose mode {'on  ' if is_verbose else 'off  '}",
            style="bold " + ("green" if is_verbose else "red"),
        )

    def cmd_exit(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        self.running = False

    def cmd_cls(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        os.system("cls" if os.name == "nt" else "clear")
        self.header()

    def cmd_debug(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        raise NotImplementedError("Debug command not implemented")

    def maybe_command(self, root):
        maybe = possible_match(root, self.COMMANDS)
        self.error(
            f'Invalid command: "{root}". '
            + (f'Did you mean: "{maybe}"? ' if maybe else "")
            + 'Type "help" for a list of commands'
        )

    def process_command(self, command: str):
        try:
            root, pos, kwargs, flags = parse(command)
        except ParsingError as e:
            self.error(f"{e}: {command!r}")
            return
        command_method = self.command_methods.get(root)
        if command_method is None:
            self.maybe_command(root)
            return
        if "help" in flags:
            self.cmd_help([root], {}, set())
            return
        command_method(pos, kwargs, flags)

    def run(self):
        self.header()
        while self.running:
            try:
                command = self.input(">>> ")
                self.process_command(command)
            except KeyboardInterrupt:
                return
            except Exception as _:
                self.cns.print_exception()
