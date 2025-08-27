import sqlite3
from typing import Callable

from rich.console import Console
from rich.syntax import Syntax

from src.obj.entry import Entry
from src.apps.base import BaseApp
from src.paths import SQL_QUERY_EXAMPLES_DIR
from src.utils.rich_utils import get_rich_table
from src.parser import Flags, KeywordArgs, PositionalArgs


class SqlApp(BaseApp):
    def __init__(
        self,
        entries: list[Entry],
        cns: Console,
        input_fn: Callable[[str], str],
    ):
        super().__init__(cns, input_fn, prompt_str="SQL>")
        self.entries = entries
        # Build DB at init so commands can use it right away
        self.conn = self.build_in_memory_db()
        self.cursor = self.conn.cursor()

        # Pre-render the schema table once
        self._schema_table = get_rich_table(
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

    # ----- lifecycle -----

    def pre_run(self):
        super().pre_run()
        self.cns.print(self._schema_table)

    def header(self):
        self.cns.rule("SQL mode", style="bold blue")

    def post_run(self):
        try:
            self.cursor.close()
        except Exception:
            pass
        try:
            self.conn.close()
        except Exception:
            pass
        return super().post_run()

    # ----- internals -----

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

    def _process_example_command(self, args: list[str]) -> str | None:
        """Returns the query from the example file if it exists, else None (and prints UI)."""
        query_example_mapping = self.get_query_examples()
        if len(args) == 0:
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
        example_name = args[0]
        example_query_and_comment = query_example_mapping.get(example_name)
        if not example_query_and_comment:
            self.cns.print(f"Example '{example_name}' not found", style="bold red")
            return None
        return example_query_and_comment[0]

    def _try_execute_get_rows_headers(
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

    def cmd_schema(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """schema
        Show the schema of the in-memory database ('entries' table).
        """
        self.cns.print(self._schema_table)

    def cmd_example(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """example [<name>]
        List available SQL examples or execute a named example.
            name: the example name (file stem) to execute.
        """
        args = list(pos)  # remaining tokens after 'example'
        query = self._process_example_command(args)
        if not query:
            return
        self.cns.print(f"[bold blue]$SQL> [/]{query}")
        if (
            rows_headers := self._try_execute_get_rows_headers(self.cursor, query)
        ) is not None:
            table = get_rich_table(*rows_headers)
            self.cns.print(table)

    def cmd_save(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """save <query>
        Validate and save a query as a new example file in SQL_QUERY_EXAMPLES_DIR.
            query: the SQL query to save (wrap in quotes if it contains spaces).
        """
        if not pos:
            self.cns.print("Usage: save <query>", style="bold red")
            return
        query = " ".join(pos)
        if self._try_execute_get_rows_headers(self.cursor, query) is None:
            self.cns.print(
                "Did not save due to faulty query.",
                style="bold red",
            )
            return
        examples = self.get_query_examples()
        new_file = SQL_QUERY_EXAMPLES_DIR / f"{len(examples) + 1}.sql"
        new_file.write_text(query)
        self.cns.print(
            f"Saved successfully to {new_file}",
            style="bold green",
        )

    def cmd_sql(self, pos: PositionalArgs, kwargs: KeywordArgs, flags: Flags):
        """sql <query>
        Execute an arbitrary SQL query against the in-memory database.
            query: the SQL query to run (wrap in quotes if it contains spaces).
        """
        if not pos:
            self.cns.print("Usage: sql <query>", style="bold red")
            return
        query = " ".join(pos)
        if (
            rows_headers := self._try_execute_get_rows_headers(self.cursor, query)
        ) is not None:
            table = get_rich_table(*rows_headers)
            self.cns.print(table)
