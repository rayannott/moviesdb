import sqlite3
from dataclasses import dataclass
from typing import Callable

from rich.console import Console
from rich.syntax import Syntax

from src.obj.entry import Entry
from src.paths import SQL_QUERY_EXAMPLES_DIR
from src.utils.rich_utils import get_rich_table


@dataclass
class SqlMode:
    entries: list[Entry]
    cns: Console
    input: Callable[[str], str]

    def build_in_memory_db(self) -> sqlite3.Connection:
        conn = sqlite3.connect(":memory:")
        c = conn.cursor()
        c.execute(
            """
            CREATE TABLE entries (
            title TEXT NOT NULL,
            rating REAL NOT NULL,
            type TEXT NOT NULL,
            date TEXT,
            tags TEXT,
            notes TEXT
            )
            """
        )
        for entry in self.entries:
            c.execute(
                "INSERT INTO entries (title, rating, type, date, tags, notes) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    entry.title,
                    entry.rating,
                    entry.type.name.lower(),
                    entry.date.date() if entry.date else None,
                    " ".join(entry.tags),
                    entry.notes,
                ),
            )
        conn.commit()
        return conn

    def get_query_examples(self) -> dict[str, tuple[str, str]]:
        """Maps example file names to their contents and comments."""
        example_files = SQL_QUERY_EXAMPLES_DIR.glob("*.sql")
        example_texts_mapping: dict[str, tuple[str, str]] = {}
        for file in example_files:
            lines = file.read_text().splitlines()
            comments = [line for line in lines if line.startswith("--")]
            content = [line for line in lines if not line.startswith("--")]
            example_texts_mapping[file.stem] = ("\n".join(content), "\n".join(comments))
        return example_texts_mapping

    def process_example_command(self, args: list[str]) -> str | None:
        """Returns the query from the example file if it exists."""
        query_example_mapping = self.get_query_examples()
        if len(args) == 1:
            self.cns.print("Available examples:")
            for example_name, (
                example_content,
                example_comments,
            ) in query_example_mapping.items():
                comments_part = (
                    f"[green]{example_comments}[/]" if example_comments else ""
                )
                content_highlighted = Syntax(
                    code=example_content,
                    lexer="sql",
                    theme="nord-darker",
                    line_numbers=True,
                )
                self.cns.print(f"{example_name}: {comments_part}")
                self.cns.print(content_highlighted)
            return None
        example_name = args[1]
        example_query_and_comment = query_example_mapping.get(example_name)
        if not example_query_and_comment:
            self.cns.print(f"Example '{example_name}' not found", style="bold red")
            return None
        return example_query_and_comment[0]

    def try_execute_get_rows_headers(
        self, cursor: sqlite3.Cursor, query: str
    ) -> tuple[list[list[str]], list[str]] | None:
        try:
            cursor.execute(query)
            rows = [list(map(str, row)) for row in cursor.fetchall()]
            if not rows:
                self.cns.print("No entries match your query", style="bold red")
                return None
            headers = [desc[0] for desc in cursor.description]
            return rows, headers
        except sqlite3.Error as e:
            self.cns.print(f"Error:\n{e}", style="bold red")
            return None

    def run(self):
        conn = self.build_in_memory_db()
        c = conn.cursor()
        self.cns.rule("SQL mode", style="bold blue")
        self.cns.print(
            """The only table is called "entries"
Type "example" to see some example queries.
Use "example <example_name>" to run an example query.
Use "save <query>" to save a valid query as a new example.
Type "exit" to quit SQL mode."""
        )
        schema_table = get_rich_table(
            [
                ["title", "TEXT", ""],
                [
                    "rating",
                    "REAL",
                    "a number between 0 and 10 with up to 2 decimal places",
                ],
                ["type", "TEXT", 'either "movie" or "series"'],
                ["date", "TEXT", "a date in the format yyyy-mm-dd or NULL"],
                ["tags", "TEXT", "space-separated tags"],
                ["notes", "TEXT", "any string"],
            ],
            ["Column", "Type", "Description"],
            title="'entries' table",
            justifiers=["right", "left"],
            styles=["bold white", "blue"],
        )
        self.cns.print(schema_table)
        while True:
            query = self.input("[bold blue]SQL> ")
            if query == "exit":
                break
            if query.startswith("example"):
                query = self.process_example_command(query.split())
                if not query:
                    continue
                self.cns.print(f"[bold blue]$SQL> [/]{query}")
            if query.startswith("save "):
                _, query = query.split(" ", maxsplit=1)
                if self.try_execute_get_rows_headers(c, query) is None:
                    self.cns.print(
                        "Did not save due to faulty query.",
                        style="bold red",
                    )
                    continue
                examples = self.get_query_examples()
                new_file = SQL_QUERY_EXAMPLES_DIR / f"{len(examples) + 1}.sql"
                new_file.write_text(query)
                self.cns.print(
                    f"Saved successfully to {new_file}",
                    style="bold green",
                )
                continue
            if (
                rows_headers := self.try_execute_get_rows_headers(c, query)
            ) is not None:
                table = get_rich_table(*rows_headers)
                self.cns.print(table)
