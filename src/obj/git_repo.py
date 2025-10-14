from time import perf_counter as pc

from dataclasses import dataclass

from git import Commit, Repo


@dataclass
class RepoInfo:
    branch_name: str = "unknown"
    last_commit: Commit | None = None

    @property
    def last_commit_timestamp(self) -> str:
        return (
            self.last_commit.committed_datetime.strftime("%Y-%m-%d %H:%M:%S")
            if self.last_commit
            else "unknown"
        )

    @property
    def last_commit_date(self) -> str:
        return (
            self.last_commit.committed_datetime.strftime("%d %b %Y")
            if self.last_commit
            else "unknown"
        )

    @property
    def last_commit_rich_formatted(self) -> str:
        return (
            f"[bold cyan]{self.last_commit.hexsha[:8]}[/] "
            f"[dim]<{self.last_commit.author.name} <{self.last_commit.author.email}>[/] "
            f"[green]{self.last_commit_timestamp}[/]\n  "
            f"{self.last_commit.message}"
            if self.last_commit is not None
            else "[red]No info[/]"
        )


class RepoManager:
    def __init__(self):
        _t0 = pc()
        try:
            self.repo: Repo | None = Repo(".")
            self.recent_commits = list(self.repo.iter_commits(max_count=5))
            self.on_branch: str | None = self.repo.active_branch.name
            self.last_commit: Commit | None = self.recent_commits[0]
        except Exception:
            self.repo = None
            self.recent_commits = []
            self.on_branch = None
            self.last_commit = None
        self.loaded_in = pc() - _t0

    def get_repo_info(self) -> RepoInfo:
        if self.on_branch is not None and self.last_commit is not None:
            return RepoInfo(branch_name=self.on_branch, last_commit=self.last_commit)
        return RepoInfo()
