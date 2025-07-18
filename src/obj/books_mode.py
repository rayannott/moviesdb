import os
from time import perf_counter as pc
from datetime import datetime
from dataclasses import dataclass
from typing import Callable, NamedTuple

from rich.console import Console
from supabase import create_client, Client

from src.obj.entry import Entry
from src.utils.rich_utils import get_rich_table, format_rating
from src.utils.env import SUPABASE_API_KEY, SUPABASE_PROJECT_ID
from src.parser import parse, PositionalArgs, KeywordArgs, Flags


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
    entries: list[Entry]
    cns: Console
    input: Callable[[str], str]

    def __post_init__(self):
        with self.cns.status("Connecting..."):
            t0 = pc()
            self.client = create_client(
                f"https://{SUPABASE_PROJECT_ID}.supabase.co",
                SUPABASE_API_KEY,
            )
            t1 = pc()
            existing_rows = self.client.table("books").select("*").execute().data
            t2 = pc()
            self.existing_books = [Book.from_sql_row(row) for row in existing_rows]
        self.cns.rule("Books App", style="bold yellow")
        self.cns.print(
            f"[green]Connected to Supabase ({t1 - t0:.3f} sec).[/] "
            f"There are {len(self.existing_books)} books (loaded in {t2 - t1:.3f} sec)."
        )
        self.verbose = False

    def cmd_list(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
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
        table = self.get_books_table(_books[_s], force_verbose=True)
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
            self.cns.print(self.get_books_table(exact, title="Exact matches"))
        if close:
            self.cns.print(self.get_books_table(close, title="Close matches"))

    def run(self):
        while True:
            query = self.input("[bold yellow]BOOKS> ")
            root, pos, kwargs, flags = parse(query)
            if root == "exit":
                break
            elif root == "help":
                self.cns.print("Help message.")
            elif root == "cls":
                os.system("cls" if os.name == "nt" else "clear")
            elif root == "list":
                self.cmd_list(pos, kwargs, flags)
            elif root == "find":
                self.cmd_find(pos, kwargs, flags)
            elif root == "verbose":
                self.verbose = not self.verbose
                self.cns.print(
                    f"Verbose mode {'on  ' if self.verbose else 'off  '}",
                    style=f"bold {'green' if self.verbose else 'red'}",
                )
