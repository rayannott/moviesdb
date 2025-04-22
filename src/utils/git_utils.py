from typing import Literal

from git import Repo
from rich.align import Align
from rich.console import RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.text import Text

from src.paths import DB_FILE, WATCH_LIST_FILE
from src.utils.rich_utils import comparison

repo = Repo()


def get_local_changes() -> tuple[list[str], list[str]]:
    """Returns True if there are local changes in the db.json or watch_list.json files."""
    db_changes = [
        line
        for line in repo.git.diff(DB_FILE).split("\n")
        if line.startswith(("+ ", "- "))
    ]
    watch_list_changes = [
        line
        for line in repo.git.diff(WATCH_LIST_FILE).split("\n")
        if line.startswith(("+ ", "- "))
    ]
    return db_changes, watch_list_changes


def stash_changes(what: Literal["db", "wl"]) -> list[RenderableType]:
    file = {"db": DB_FILE, "wl": WATCH_LIST_FILE}[what]
    db_changes, watch_list_changes = get_local_changes()
    changes = {"db": db_changes, "wl": watch_list_changes}[what]
    msgs = []
    if changes:
        repo.git.stash("push", "-m", what, "--", file)
        msgs.append(f"[bold green] Stashed {len(changes)} {what} changes in {what}[/]")
    else:
        msgs.append(f"[bold yellow] No changes in {what}[/]")
    return msgs


def remote_db(sync_remote: bool = False) -> list[RenderableType]:
    """Brings the remote repository up to date with the local repository.

    Returns a list of the feedback messages."""
    msgs = []
    last_commit = next(repo.iter_commits())
    msgs.append("[yellow]Last commit[/]:")
    msgs.append(f"  [bold blue]date[/]: {last_commit.committed_datetime}")
    msgs.append(f"  [bold blue]message[/]: {last_commit.summary}")
    msgs.append(f"  [bold blue]change stats[/]: {last_commit.stats.files}")

    db_changes, watch_list_changes = get_local_changes()
    if not db_changes and not watch_list_changes:
        msgs.append("[bold red]There are no changes[/]")
        return msgs

    msgs.append(
        comparison(
            Panel(
                Syntax(
                    code="\n".join(db_changes),
                    lexer="diff",
                    theme="nord-darker",
                )
                if db_changes
                else Align(Text("none", style="bold red"), align="center"),
                title="Database",
            ),
            Panel(
                Syntax(
                    code="\n".join(watch_list_changes),
                    lexer="diff",
                    theme="nord-darker",
                )
                if watch_list_changes
                else Align(Text("none", style="bold red"), align="center"),
                title="Watch List",
            ),
        )
    )

    if not sync_remote:
        return msgs

    if db_changes:
        repo.git.add(DB_FILE)
    if watch_list_changes:
        repo.git.add(WATCH_LIST_FILE)

    commit_feedback = repo.git.commit("-m", "upd")
    msgs.append(commit_feedback)
    push_feedback = repo.git.push()
    if not push_feedback:
        msgs.append("[bold green]Pushed successfully  [/]")
    else:
        msgs.append(push_feedback)
    return msgs
