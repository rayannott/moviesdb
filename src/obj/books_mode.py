from dataclasses import dataclass
from typing import Callable

from rich.console import Console
from supabase import create_client

from src.obj.entry import Entry
from src.utils.rich_utils import get_rich_table
from src.utils.env import SUPABASE_API_KEY, SUPABASE_PROJECT_ID


@dataclass
class BooksMode:
    entries: list[Entry]
    cns: Console
    input: Callable[[str], str]

    def __post_init__(self):
        self.client = create_client(
            f"https://{SUPABASE_PROJECT_ID}.supabase.co",
            SUPABASE_API_KEY,
        )
        n_entries = (
            self.client.table("books")
            .select("*", count="exact")  # type: ignore
            .execute()
            .count
        )
        self.cns.print(f"[green]Connected to Supabase.[/] There are {n_entries} books.")

    def execute_command(self, command: str):
        print(f"command {command}")

    def run(self):
        self.cns.rule("Books App", style="bold yellow")
        # self.cns.print("""...""")
        while True:
            query = self.input("[bold yellow]BOOKS> ")
            if query == "exit":
                break
