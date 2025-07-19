from time import perf_counter as pc
from datetime import datetime
from dataclasses import dataclass
from typing import Callable, NamedTuple

from rich.console import Console
from supabase import create_client, Client

from src.utils.rich_utils import get_rich_table, format_rating
from src.utils.help_utils import parse_docstring, get_rich_help
from src.utils.env import SUPABASE_API_KEY, SUPABASE_PROJECT_ID
from src.parser import parse, PositionalArgs, KeywordArgs, Flags, ParsingError


class Book(NamedTuple):
    """A class for comparing."""

    dt_read: datetime  # this is the id, primary key
    title: str  # this is the id, primary key
    author: str | None
    rating: float | None
    n_pages: int | None
    body: str

    def __repr__(self) -> str:
        return f"{self.title} from {self.dt_read:%d.%m.%Y}"

    @classmethod
    def from_sql_row(cls, row: dict) -> "Book":
        return cls(
            dt_read=datetime.fromisoformat(row["dt_read"]),
            title=row["title"],
            author=row.get("author"),
            rating=row.get("rating"),
            n_pages=row.get("n_pages"),
            body=row["body"],
        )

    def to_row(self) -> dict:
        return {
            "dt_read": self.dt_read.isoformat(),
            "title": self.title,
            "author": self.author,
            "rating": self.rating,
            "n_pages": self.n_pages,
            "body": self.body,
        }

    def to_row_values_only(self) -> list:
        return [
            self.title,
            self.dt_read,
            self.rating,
            self.author,
            self.n_pages,
            self.body,
        ]

    def insert(self, client: Client):
        client.table("books").insert(self.to_row()).execute()

    def update(self, client: Client):
        _ = (
            client.table("books")
            .update(self.to_row())
            .match({"title": self.title, "dt_read": self.dt_read.isoformat()})
            .execute()
        )


@dataclass
class BooksMode:
    cns: Console
    input: Callable[[str], str]

    @staticmethod
    def get_client() -> Client:
        """Creates and returns a Supabase client."""
        return create_client(
            f"https://{SUPABASE_PROJECT_ID}.supabase.co", SUPABASE_API_KEY
        )

    @staticmethod
    def get_books(client: Client) -> list[Book]:
        """Fetches all books from the Supabase database."""
        existing_rows = client.table("books").select("*").execute().data
        return [Book.from_sql_row(row) for row in existing_rows]

    def __post_init__(self):
        with self.cns.status("Connecting..."):
            t0 = pc()
            self.client = self.get_client()
            t1 = pc()
            self.existing_books = self.get_books(self.client)
            t2 = pc()
        self.cns.rule(
            f"Books App ({len(self.existing_books)} books)", style="bold yellow"
        )
        self.cns.print(
            f"[dim]Connected to Supabase in {t1 - t0:.3f} sec; loaded books in {t2 - t1:.3f} sec."
        )
        self.verbose = False
        self.running = True

        self.command_methods: dict[
            str, Callable[[PositionalArgs, KeywordArgs, Flags], None]
        ] = {
            method_name[4:]: getattr(self, method_name)
            for method_name in dir(self)
            if method_name.startswith("cmd_")
        }

        self.help_messages = {
            cmd_root: parse_docstring(cmd_fn.__doc__)
            for cmd_root, cmd_fn in self.command_methods.items()
        }

    def cmd_list(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """list [--n <n>] [--sortby <key>] [--verbose]
        List the last n books, sorted by the given key.
            n: number of entries to list (default: 5)
            sortby: return entries sorted by date (key=dt), rating (key=rating), or number of pages (key=pages)
            verbose(flag): if given, display the notes column (overrides subapp verbosity)
        """
        # TODO: add the n argument
        sortby = kwargs.get("sortby", "dt")
        _sort_fns = {
            "dt": lambda x: x.dt_read,
            "rating": lambda x: -x.rating,
            "pages": lambda x: -x.n_pages,
        }
        sort_fn = _sort_fns.get(sortby)
        if sort_fn is None:
            self.cns.print(
                f'"{sortby}" is an unknown sort parameter. '
                f"Try one of {list(_sort_fns.keys())} instead.",
                style="bold yellow",
            )
            return

        _s = slice(-5, None, None) if sortby == "dt" else slice(0, 5, None)
        _books = self.existing_books.copy()
        _books.sort(key=sort_fn)
        table = self.get_books_table(_books[_s], force_verbose="verbose" in flags)
        self.cns.print(table)

    def get_books_table(self, books: list[Book], title="Books", force_verbose=False):
        cols = [
            "Title",
            "Date and Time",
            "Rating",
            "Author",
            "Num. pages",
            "Notes",
        ]
        styles = ["bold", None, None, None, "dim", None]
        justifiers = ["right"] * 5 + ["left"]
        _s = slice(None) if force_verbose or self.verbose else slice(0, -1)
        rows = [book.to_row_values_only() for book in books]
        rows = [
            [
                title,
                dt_str.strftime("%d.%m.%Y %H:%M"),
                format_rating(rating),
                author,
                str(n_pages),
                body,
            ][_s]
            for title, dt_str, rating, author, n_pages, body in rows
        ]
        return get_rich_table(
            rows,
            cols[_s],
            title=title,
            styles=styles[_s],
            justifiers=justifiers[_s],
        )

    def cmd_find(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """find <title> [--verbose]
        Find entries by the title substring."""
        if not pos:
            self.cns.print("The title substring is missing.", style="bold red")
            return
        title = pos[0]
        exact, close = [], []
        for book in self.existing_books:
            if book.title.lower() == title.lower():
                exact.append(book)
            elif title.lower() in book.title.lower():
                close.append(book)
        if exact:
            self.cns.print(
                self.get_books_table(
                    exact, title="Exact matches", force_verbose="verbose" in flags
                )
            )
        if close:
            self.cns.print(
                self.get_books_table(
                    close, title="Close matches", force_verbose="verbose" in flags
                )
            )

    def cmd_exit(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """exit
        Exit the books subapp."""
        self.running = False

    def cmd_help(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """help [<command>]
        Show help for the given command.
        If no argument is given, show for all.
        Note: 'help <cmd>' is equivalent to '<cmd> --help'."""
        query = pos[0] if pos else None
        self.cns.print(get_rich_help(query, self.help_messages))

    def cmd_verbose(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """verbose
        Toggle subapp verbosity.
        Verbosity determines whether to show the notes column."""
        self.verbose = not self.verbose
        self.cns.print(
            f"Verbose mode {'on  ' if self.verbose else 'off  '}",
            style=f"bold {'green' if self.verbose else 'red'}",
        )

    def run(self):
        while self.running:
            command = self.input("[bold yellow]BOOKS> ")
            try:
                root, pos, kwargs, flags = parse(command)
            except ParsingError as e:
                self.cns.print(f"{e}: {command!r}", style="bold red")
                return
            command_method = self.command_methods.get(root)
            if command_method is None:
                self.cns.print(f"Unknown command: {root}.", style="bold red")
                return
            if "help" in flags:
                self.cmd_help([root], {}, set())
                return
            command_method(pos, kwargs, flags)
