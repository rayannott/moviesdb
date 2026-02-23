import json
import random
import re
from functools import cached_property, partial
from itertools import batched, starmap
from pathlib import Path
from statistics import mean, stdev
from time import perf_counter as pc
from typing import Any, Callable

from loguru import logger
from pyfzf.pyfzf import FzfPrompt
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt

from src.applications.tui.apps.base import BaseApp
from src.applications.tui.apps.image import ImagesApp
from src.applications.tui.apps.sqlapp import SqlApp
from src.exceptions import EntryNotFoundException, MalformedEntryException
from src.models.entry import Entry, EntryType
from src.obj.ai import ChatBot
from src.obj.omdb_response import get_by_title
from src.obj.textual_apps import ChatBotApp, EntryFormApp
from src.obj.verbosity import is_verbose
from src.parser import Flags, KeywordArgs, PositionalArgs
from src.paths import LOCAL_DIR
from src.services.chatbot_service import ChatbotService
from src.services.entry_service import EntryService
from src.services.export_service import ExportService
from src.services.guest_service import GuestService
from src.services.image_service import ImageService
from src.services.watchlist_service import WatchlistService
from src.setup_logging import setup_logging
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
    replace_tag_alias,
)


def identity(x: str) -> str:
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

setup_logging()


class TUIApp(BaseApp):
    def __init__(
        self,
        entry_service: EntryService,
        watchlist_service: WatchlistService,
        chatbot_service: ChatbotService,
        guest_service: GuestService,
        export_service: ExportService,
        image_service_factory: Callable[[], ImageService],
    ) -> None:
        self.running = True
        self.cns = Console()
        self.input = partial(rinput, self.cns)

        super().__init__(self.cns, input, prompt_str=">>>")  # keep builtin input

        self._entry_svc = entry_service
        self._watchlist_svc = watchlist_service
        self._chatbot_svc = chatbot_service
        self._guest_svc = guest_service
        self._export_svc = export_service
        self._image_svc_factory = image_service_factory

        self.chatbot = ChatBot(self.entries, self._chatbot_svc)

        logger.info(
            f"init App; {len(self.entries)} entries, {self._watchlist_svc.count} watch list items"
        )

        self.recently_popped: list[Entry] = []

    @cached_property
    def _image_svc(self) -> ImageService:
        with self.cns.status("Connecting to S3..."):
            img = self._image_svc_factory()
            return img

    @property
    def entries(self) -> list[Entry]:
        return self._entry_svc.get_entries()

    @staticmethod
    def get_watch_table(watch_list_items: list[tuple[str, bool]]) -> Any:
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

    def fzf_select_entries(
        self, is_verbose_flag: bool = False
    ) -> list[tuple[int, Entry]]:
        _entries = self.entries

        def _fmt(idx: int, entry: Entry) -> str:
            _tags = (" " + " ".join(f"#{t}" for t in entry.tags)) if entry.tags else ""
            _date = f" ({entry.date.strftime('%d.%m.%Y')})" if entry.date else ""
            _note = f": {entry.notes}" if is_verbose_flag and entry.notes else ""
            return f"[{idx}] {entry.title}{_date}{_tags}{_note}"

        fzf = FzfPrompt()
        res = fzf.prompt(
            [_fmt(idx, e) for idx, e in reversed(list(enumerate(_entries)))],
            "--multi",
        )
        return [
            ((idx := int(m.group(1))), _entries[idx])
            for m in map(re.compile(r"^\[(\d+)\].+$").match, res)
            if m
        ]

    def header(self) -> None:
        rule_text = rf"[bold green]{len(self.entries)}[/] entries"
        self.cns.rule(rule_text)

    def cmd_find(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """find <title>
        Find entries by the title substring."""
        title = " ".join(pos)
        if not title:
            res = self.fzf_select_entries(is_verbose_flag=bool(is_verbose))
            if not res:
                return
            ids, matches = zip(*res)
            self.cns.print(
                get_entries_table(
                    matches,
                    ids,
                    title=f"[bold green]{len(res)}[/] selected entries "
                    f"(avg {format_rating(mean(m.rating for m in matches))})",
                )
            )
            return
        exact = self._entry_svc.find_exact_matches(title)
        sub = self._entry_svc.find_substring_matches(title)
        watch = self._watchlist_svc.filter_items(
            key=lambda t, _: title.lower() in t.lower()
        )
        if exact:
            ids, matches = zip(*exact)
            self.cns.print(
                get_entries_table(
                    matches,
                    ids,
                    title=f"[bold green]{len(exact)}[/] exact matches "
                    f"(avg {format_rating(mean(m.rating for m in matches))})",
                )
            )
        if sub:
            ids, matches = zip(*sub)
            self.cns.print(
                get_entries_table(
                    matches,
                    ids,
                    title=f"[bold yellow]{len(sub)}[/] possible matches "
                    f"(avg {format_rating(mean(m.rating for m in matches))})",
                )
            )
        if watch:
            self.cns.print(self.get_watch_table(watch))

    def cmd_modify(
        self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags
    ) -> None:
        if not pos:
            self.error("No index provided.")
            return
        idx = pos[0]
        entry = self._entry_svc.entry_by_idx(idx)
        if entry is None:
            self.error(f"Invalid index: {idx}.")
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
            entry_app.entry.id = entry.id
            self._entry_svc.update_entry(entry_app.entry)
            was_fmt = format_entry(entry)
            now_fmt = format_entry(entry_app.entry)
            self.cns.print(f"[green]󰚰 Updated[/]\n - was: {was_fmt}\n - now: {now_fmt}")

    def cmd_tag(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """tag [<tagname>] [<index or title>] [--delete]
        Show all tags, list entries with a given tag, or add/remove a tag
        to/from an entry.
        If no arguments are specified, show all tags and their counts.
        If <tagname> is specified, show all entries with that tag.
        If <tagname> and <index or title> are specified, add the tag to the entry.
        If --delete is specified, remove the tag from the entry."""
        tags = self._entry_svc.get_tags()
        if not pos:
            self.cns.print(
                get_rich_table(
                    [
                        [
                            format_tag(tag),
                            str(len(entries)),
                            (
                                f"{format_rating(mean(e.rating for e in entries))} "
                                f"± {std([e.rating for e in entries]):.2f}"
                            ),
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
        title_or_idx = pos[1]
        entry = self._entry_svc.entry_by_idx_or_title(title_or_idx)
        if not entry:
            self.warning(f"No entry found matching idx or title: {title_or_idx!r}")
            return
        if {"d", "delete"} & flags:
            if not self._entry_svc.remove_tag(entry, tagname):
                entry_fmt = format_entry(entry)
                tag_fmt = format_tag(tagname)
                self.cns.print(
                    f"{entry_fmt} [bold red]does not have the tag[/] {tag_fmt}"
                )
                return
            entry_fmt = format_entry(entry)
            tag_fmt = format_tag(tagname)
            self.cns.print(
                f"{entry_fmt} [bold green]has been untagged from[/] {tag_fmt}"
            )
            return
        if not self._entry_svc.add_tag(entry, tagname):
            self.warning(f"The entry already has the tag {format_tag(tagname)}:")
            self.cns.print(format_entry(entry))
            return
        entry_fmt = format_entry(entry)
        tag_fmt = format_tag(tagname)
        self.cns.print(f"{entry_fmt} [bold green]has been tagged with[/] {tag_fmt}")

    def cmd_plot(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """plot
        Generate a bar plot of the ratings over time."""
        with self.cns.status("Generating..."):
            fig = get_plot(self.entries)
        fig.show()

    def cmd_note(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """note <text>
        Find entries by substring in notes."""
        note = " ".join(pos)
        if not note:
            self.error("Empty note")
            return
        matches = self._entry_svc.find_by_note(note)
        if matches:
            ids, entries = zip(*matches)
            self.cns.print(
                get_entries_table(
                    entries, ids, title=f"[bold yellow]{len(matches)}[/] matches"
                )
            )
        else:
            self.error("No matches found")

    def cmd_ai(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """ai [<prompt>] [--full | --reset | --memory | --forget <id> |
        --remember <text>]
        Ask the chatbot a question or open a TUI interface.
        If <prompt> is not given, open the chatbot TUI interface.
        If --full is specified, use the full chatGPT-4o model instead of mini.
        If --reset is specified, clear the conversation history.
        If --memory is specified, list the AI's saved memories about the user.
        If --forget <id> is specified, forget the memory item corresponding to the id.
        If --remember <text> is specified, add info about the user manually."""
        if "reset" in flags:
            n_pairs = len(self.chatbot._conversation_history)
            self.cns.print(f"Cleared {n_pairs} prompt-response pairs.")
            self.chatbot.reset()
            return
        if "memory" in flags:
            mem_items = self._chatbot_svc.get_memory_items()
            if not mem_items:
                self.warning("No context about the user.")
                return
            for mi_id, mi_info in mem_items:
                self.cns.print(rf"[blue]\[{mi_id[-7:]}][/] [green]{mi_info}[/]")
            return
        if (mi_id_to_remove := kwargs.get("forget")) is not None:
            ok, deleted_id = self._chatbot_svc.delete_memory(mi_id_to_remove)
            if ok and deleted_id:
                self.cns.print(f"󰺝 Deleted [blue]{deleted_id}.")
            else:
                self.warning(f"No memory with {mi_id_to_remove}.")
            return
        if (to_remember := kwargs.get("remember")) is not None:
            oid = self._chatbot_svc.add_memory(to_remember)
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
            "Thinking hard ",
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

    def cmd_list(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
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

    def cmd_group(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """group [<title>] [--series | --movies] [--n <n>] [--all]
        Group entries by title (and type) and show the top n (default is 5).
        If <title> is not given, show the top n groups sorted by average rating.
        If --series or --movies is specified, filter the groups by type.
        If --all is specified, show all matched groups."""
        if F_SERIES in flags and F_MOVIES in flags:
            self.error(f"Cannot specify both --{F_SERIES} and --{F_MOVIES} ")
            return
        groups = self._entry_svc.get_groups()
        int_str = kwargs.get("n", "5")
        if (n := self.try_int(int_str)) is None:
            return
        if F_SERIES in flags:
            groups = [g for g in groups if g.type == EntryType.SERIES]
        elif F_MOVIES in flags:
            groups = [g for g in groups if g.type == EntryType.MOVIE]
        if title := " ".join(pos):
            groups = [g for g in groups if title.lower() in g.title.lower()]
        _title = f"Top {n} groups" + (f' with "{title}"' if title else "")
        _slice = slice(0, None, None) if F_ALL in flags else slice(0, n, None)
        if not groups[_slice]:
            self.error("No matches found")
            return
        self.cns.print(get_groups_table(groups[_slice], title=_title))

    def cmd_watch(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """watch [<title>] [--delete | --random]
        Show the watch list.
        If <title> is given, add it to the watch list.
        If --delete is specified, remove the title from the watch list.
        Without a title, if --random is specified, show a random watch list title.
        If <title> ends with a '+', it is considered a series."""
        title = " ".join(pos)
        if not flags and not title:
            items = self._watchlist_svc.get_items()
            if not items:
                self.warning("Watch list is empty")
                return
            self.cns.print(self.get_watch_table(items))
            return
        if {"r", "random"} & flags:
            items = self._watchlist_svc.get_items()
            if items:
                self.cns.print(format_movie_series(*random.choice(items)))
            return
        is_series = title.endswith("+")
        title = title.rstrip("+")
        if {"d", "delete"} & flags:
            self._unwatch(title, is_series)
        else:
            self._watch(title, is_series)

    def _watch(self, title: str, is_series: bool) -> None:
        if self._watchlist_svc.contains(title, is_series):
            title_fmt = format_title(
                title, EntryType.SERIES if is_series else EntryType.MOVIE
            )
            self.cns.print(
                f" {title_fmt} [bold red]is already in the watch list[/]",
            )
            return
        exact_matches = self._entry_svc.find_exact_matches(title)
        if exact_matches:
            entry = exact_matches[0][1]
            entry_fmt = format_entry(entry)
            self.cns.print(
                f'[white]"{title}"[/] is already in the database  \n{entry_fmt}',
                style="bold yellow",
            )
            prompt = Prompt.ask(
                "What should we do with it\n"
                + "  [bold green]a[/]:  add to watch list anyway\n"
                + f"  [bold blue]t[/]: 󰓹 tag it with {format_tag(TAG_WATCH_AGAIN)}\n"
                + "  [bold red]n[/]:   nothing\n",
                choices=["a", "t", "n"],
                default="n",
            )
            if prompt == "t":
                self._entry_svc.add_tag(entry, TAG_WATCH_AGAIN)
                self.cns.print(f"Done:\n{format_entry(entry)}")
                return
            elif prompt == "n":
                return
            return
        possible_title = self._watchlist_svc.possible_title_match(title)
        if possible_title is not None and possible_title != title:
            msg = (
                f'[yellow] NOTE[/] entry with similar title ("{possible_title}") '
                f'exists. Override "{title}" with "{possible_title}"?'
            )
            update_title = Prompt.ask(
                msg,
                choices=["y", "n"],
                default="n",
            )
            if update_title == "y":
                title = possible_title
        self._watchlist_svc.add(title, is_series)
        self.cns.print(
            format_title(title, EntryType.SERIES if is_series else EntryType.MOVIE)
            + "[bold green] has been added to the watch list."
        )

    def _unwatch(self, title: str, is_series: bool) -> None:
        if not title:
            self.cns.print(" Empty title.", style="red")
            return
        title_fmtd = format_title(
            title, EntryType.SERIES if is_series else EntryType.MOVIE
        )
        try:
            self._watchlist_svc.remove(title, is_series)
        except EntryNotFoundException:
            self.error(f"{title_fmtd} is not in the watch list.")
            return
        self.cns.print(
            title_fmtd + "[bold green] has been removed from the watch list."
        )

    def cmd_stats(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """stats [--dev]
        Show some statistics about the entries.
        If --dev is specified, show app stats (loading times, last commit, etc.)."""
        # TODO: make pretty
        stats = self._entry_svc.get_stats()
        self.cns.print(f"Total entries:\n  {stats.total}")
        avg_movies = mean(stats.movie_ratings) if stats.movie_ratings else 0
        avg_series = mean(stats.series_ratings) if stats.series_ratings else 0
        stdev_movies = std(stats.movie_ratings)
        stdev_series = std(stats.series_ratings)
        movies_line = (
            f"  - movies: {format_rating(avg_movies)} ± {stdev_movies:.3f} "
            f"(n={len(stats.movie_ratings)})"
        )
        series_line = (
            f"  - series: {format_rating(avg_series)} ± {stdev_series:.3f} "
            f"(n={len(stats.series_ratings)})"
        )
        self.cns.print(f"Averages:\n{movies_line}\n{series_line}")
        watched_more_than_once = [g for g in stats.groups if len(g.ratings) > 1]
        watched_times = [len(g.ratings) for g in stats.groups]
        watched_times_mean = mean(watched_times) if watched_times else 0
        watched_times_stdev = std(watched_times)
        unique_msg = (
            f"There are {len(stats.groups)} unique entries; "
            f"{len(watched_more_than_once)} of them have been watched more than once "
            f"({watched_times_mean:.2f} ± {watched_times_stdev:.2f} times on average)."
        )
        watchlist_msg = (
            f"There are {stats.watchlist_count} items in the watch list "
            f"({stats.watchlist_movies_count} movies, "
            f"{stats.watchlist_series_count} series)."
        )
        self.cns.print(f"{unique_msg}\n{watchlist_msg}")

        if "dev" not in flags:
            return

        self.cns.rule("Dev stats", style="bold magenta")

    def cmd_help(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """help [<command>]
        Show help for the given command.
        If no argument is given, show for all.
        Note: 'help <cmd>' is equivalent to '<cmd> --help'."""
        query = pos[0] if pos else None
        self.cns.print(get_rich_help(query, self.help_messages))

    def cmd_get(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """get <index> [--verbose]
        Get entry by index.
        If --verbose is specified, show all details.
        E.g. 'get -1 --verbose' will show the last entry with all details."""
        if not pos:
            self.error("No index provided.")
            return
        idx = pos[0]
        entry = self._entry_svc.entry_by_idx(idx)
        if entry is None:
            self.error(f"Invalid index: {idx}.")
            return
        _f = "v" if {"v", "verbose"} & flags else ""
        self.cns.print(f"#{idx} {entry:{_f}}")

    def _process_watch_again_tag_on_add(self, for_entry: Entry) -> None:
        modified = self._entry_svc.process_watch_again_on_add(for_entry)
        for e in modified:
            tag_fmt = format_tag(TAG_WATCH_AGAIN)
            self.cns.print(f"[green]󰺝 Removed tag {tag_fmt} from[/]\n{format_entry(e)}")
        if modified:
            resp = Prompt.ask(
                f"Do you want to add the {format_tag(TAG_WATCH_AGAIN)} to this entry?",
                choices=["y", "n"],
                default="n",
            )
            if resp == "y":
                for_entry.tags.add(TAG_WATCH_AGAIN)

    def cmd_add(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """add [<title>] [--tui]
        Start adding a new entry.
        If the title is not given or --tui is specified, will open a text-based
        user interface to add the entry.
        Will ask for [bold blue]rating[/]: floating point number r, 0 <= r <= 10,
        [bold blue]type[/]: "series" or "movie" or nothing (default="movie"),
        [bold blue]date[/]: dd.mm.yyyy or "now" or nothing (default=None),
        [bold blue]notes[/]: anything or nothing (default="")].
        If the title is given, will try to find an entry with the same title
        in the database and will ask to override it if it exists."""
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
        possible_title_entries = self._entry_svc.possible_title_match(title)
        possible_title_in_wl = self._watchlist_svc.possible_title_match(title)
        possible_title = possible_title_entries or possible_title_in_wl
        if (
            possible_title is not None
            and possible_title != title
            and title not in self._watchlist_svc.titles
        ):
            msg = (
                f'[bold blue] NOTE: entry with similar title ("{possible_title}") '
                f'exists. Override "{title}" with "{possible_title}"?'
            )
            update_title = Prompt.ask(
                msg,
                choices=["y", "n"],
                default="n",
            )
            if update_title == "y":
                title = possible_title
        entries = self._entry_svc.find_exact_matches(title, ignore_case=False)
        if entries:
            n_entries = len(entries)
            self.cns.print(
                f" NOTE: entry with this exact title already exists {n_entries} times",
                style="bold blue",
            )
        if title in self._watchlist_svc.titles:
            self.cns.print(
                " NOTE: this entry is in your watching list; it will be removed "
                "from the list if you add it to the database "
                "(title and type must match).",
                style="bold blue",
            )
        try:
            rating = Entry.parse_rating(self.input("[bold cyan]rating: "))
            type = Entry.parse_type(
                Prompt.ask(
                    "[bold cyan]type",
                    choices=["movie", "series"],
                    default="movie"
                    if self._watchlist_svc.get_is_series(title) is None
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
        entry = Entry(title=title, rating=rating, date=when, type=type, notes=notes)
        self._try_add_entry(entry)

    def cmd_images(
        self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags
    ) -> None:
        """images ...
        Manage images in the database.
        """
        images_app = ImagesApp(
            self._image_svc,
            self.cns,
            self.input,
            process_command_fn=self.process_command,
        )
        images_app.run()

    def _try_add_entry(self, entry: Entry) -> None:
        self._process_watch_again_tag_on_add(entry)
        self._entry_svc.add_entry(entry)
        self.cns.print(f"[green] Added [/]\n{format_entry(entry)}")
        removed = self._entry_svc.remove_from_watchlist_on_add(entry)
        if removed:
            self.cns.print(
                "[green]󰺝 Removed from watch list[/]: "
                + format_title(entry.title, entry.type)
            )

    def cmd_random(
        self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags
    ) -> None:
        """random [<n>] [--tag <tag>]
        Sample n random entries (default=1).
        If a tag is specified, show only those entries having the tag."""
        tag = kwargs.get("tag")
        if len(pos) == 1:
            if (n := self.try_int(pos[0])) is None:
                return
        else:
            n = 1
        entries = self._entry_svc.get_random_entries(n, tag)
        if not entries:
            extra = f" with tag {format_tag(tag)}" if tag else ""
            self.error(f"No entries found{extra}.")
            return
        self.cns.print(
            get_entries_table(entries, title=f"Random {len(entries)} entries")
        )

    def cmd_db(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """db <title>
        Get movie data from the online database (OMDb)."""
        title = " ".join(pos)
        if not title:
            self.error("Empty title.")
            return
        with self.cns.status("[bold cyan]󰇧 Requesting an Online Database..."):
            resp = get_by_title(title)
        if not resp:
            self.cns.print(" No response", style="red")
            return
        self.cns.print(resp.rich())

    def cmd_pop(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """pop [<index>] [--undo]
        Remove an entry by index from the database (this is reversible).
        If --undo is specified (and no index is given), restore last popped."""
        if "undo" in flags:
            if not self.recently_popped:
                self.warning("No recently popped entries.")
                return
            self.cns.print(
                f"Found {len(self.recently_popped)} recently popped entries."
            )
            to_restore = self.recently_popped.pop()
            self._entry_svc.add_entry(to_restore)
            self.cns.print(f"Restored:\n{format_entry(to_restore)}")
            return
        if not pos:
            self.error("No index provided.")
            return
        idx = pos[0]
        popped_entry = self._entry_svc.entry_by_idx(idx)
        if popped_entry is None:
            self.error(f"Invalid index: {idx}.")
            return
        assert popped_entry.id
        try:
            self._entry_svc.delete_entry(popped_entry.id)
        except EntryNotFoundException:
            self.error(f"{format_entry(popped_entry)} was not in the database.")
            return
        self.cns.print(f"󰺝 Removed\n{format_entry(popped_entry)}")
        self.recently_popped.append(popped_entry)

    def cmd_export(
        self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags
    ) -> None:
        """export [--silent] [--full]
        Export entries (movies and series) and watch list to
        ./export-local/{db|watch_list}.json.
        If --silent is specified, do not print any messages.
        If --full is specified, also export: images."""

        def _print(what: str) -> None:
            if "silent" not in flags:
                self.cns.print(what)

        result = self._export_svc.export_entries_and_watchlist()
        total_time = sum(result.timings.values())
        _print(
            f"Exported {result.entries_count} entries and "
            f"{result.watchlist_count} watchlist items. Total: {total_time:.2f}s."
        )

        if "full" not in flags:
            return

        # images
        with self.cns.status("[bold cyan]󰈭 Exporting images..."):
            image_manager = self._image_svc.create_manager()
            images_bare = image_manager._get_s3_images_bare()

        _local_exported_images = image_manager._get_exported_local_images()
        new_images_set = set(images_bare) - set(_local_exported_images)

        if not new_images_set:
            _print("No new images to export.")
            return

        _ids_to_tags = image_manager.load_tags_pretty(self.cns)
        imgs = image_manager.get_images(with_tags=_ids_to_tags)

        images_subdir = LOCAL_DIR / "images"
        images_subdir.mkdir(exist_ok=True)
        img_meta_file = images_subdir / "meta.json"
        with img_meta_file.open("w", encoding="utf-8") as f:
            json.dump([img.to_dict() for img in imgs], f, indent=2)
            n_imgs = len(imgs)
            _print(
                f"Exported the metadata of all {n_imgs} images to "
                f"{img_meta_file.absolute()}."
            )

        with (images_progress := get_pretty_progress()):
            task = images_progress.add_task(
                f"Downloading {len(new_images_set)} images...",
                total=len(new_images_set),
            )
            for img in new_images_set:
                image_manager._download_image_to(
                    img.s3_id, images_subdir / Path(img.s3_id).name
                )
                images_progress.update(task, advance=1)
        images_dir_size = sum(f.stat().st_size for f in images_subdir.iterdir())
        _print(
            f"Exported {len(new_images_set)} images to {images_subdir.absolute()}; "
            f"current total directory size: {images_dir_size * 2**-20:.3f} MB."
        )

    def cmd_guest(
        self,
        pos: PositionalArgs,
        kwargs: KeywordArgs,
        flags: Flags,
    ) -> None:
        """guest [--add <name>] [--remove <name>]
        Manage the guest list.
        add: add a name to the guest list.
        remove: remove a name from the guest list.
        If no arguments are given, show the guest list."""
        if (name := kwargs.get("add")) is not None:
            self._guest_svc.add_guest(name)
            self.cns.print(f"{name} added to the guests list", style="bold green")
        elif (name := kwargs.get("remove")) is not None:
            is_ok = self._guest_svc.remove_guest(name)
            if is_ok:
                self.cns.print(
                    f"{name} removed from the guests list", style="bold green"
                )
            else:
                self.error(f"{name} was not in the guest list")
        else:
            self.cns.print("Guests: " + ", ".join(self._guest_svc.get_guests()))

    def cmd_sql(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """sql
        Start the SQL-like query mode."""
        sql_mode = SqlApp(self.entries, self.cns, self.input)
        sql_mode.run()

    def cmd_game(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        """game
        Start the guessing game subapp."""
        from src.obj.game import GuessingGame

        game = GuessingGame(self._entry_svc.get_groups(), self.cns, self.input)
        game.run()

    def cmd_verbose(
        self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags
    ) -> None:
        """verbose
        Toggle verbose mode.
        In verbose mode, the entries' notes are shown as well."""
        is_verbose.toggle()
        self.cns.print(
            f"Verbose mode {'on  ' if is_verbose else 'off  '}",
            style=f"bold {'green' if is_verbose else 'red'}",
        )

    def cmd_debug(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags) -> None:
        raise NotImplementedError("Debug command not implemented")

    def pre_run(self) -> None:
        """Prepare the application to run."""
        super().pre_run()
        self.cmd_export([], {}, {"silent"})

    # Compatibility properties for ImagesApp and other sub-apps
    # that reference self.app.entries / self.app.entry_by_idx_or_title
    def entry_by_idx(
        self, idx: int | str, *, suppress_errors: bool = False
    ) -> Entry | None:
        entry = self._entry_svc.entry_by_idx(idx)
        if entry is None and not suppress_errors:
            self.error(f"Invalid index: {idx}.")
        return entry

    def entry_by_idx_or_title(self, idx_title: str | int) -> Entry | None:
        return self._entry_svc.entry_by_idx_or_title(idx_title)
