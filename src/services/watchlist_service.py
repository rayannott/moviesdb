from collections.abc import Callable

from src.exceptions import DuplicateEntryException, EntryNotFoundException
from src.models.watchlist_entry import WatchlistEntry
from src.repos.entries import EntriesRepo
from src.repos.watchlist_entries import WatchlistEntriesRepo
from src.utils.utils import possible_match


class WatchlistService:
    """Business logic for the watchlist."""

    def __init__(
        self,
        watchlist_repo: WatchlistEntriesRepo,
        entries_repo: EntriesRepo,
    ) -> None:
        self._watchlist_repo = watchlist_repo
        self._entries_repo = entries_repo

    def get_items(self) -> list[tuple[str, bool]]:
        """Return (title, is_series) pairs for all watchlist entries."""
        entries = self._watchlist_repo.get_all()
        return [(e.title, e.is_series) for e in entries]

    def get_entries(self) -> list[WatchlistEntry]:
        return self._watchlist_repo.get_all()

    @property
    def titles(self) -> set[str]:
        return {e.title for e in self._watchlist_repo.get_all()}

    @property
    def count(self) -> int:
        return len(self._watchlist_repo.get_all())

    @property
    def movies(self) -> list[str]:
        return [e.title for e in self._watchlist_repo.get_all() if not e.is_series]

    @property
    def series(self) -> list[str]:
        return [e.title for e in self._watchlist_repo.get_all() if e.is_series]

    def contains(self, title: str, is_series: bool) -> bool:
        items = self.get_items()
        return (title, is_series) in items

    def add(self, title: str, is_series: bool) -> WatchlistEntry:
        """Add to watchlist.

        Raises DuplicateEntryException if already present.
        """
        if self.contains(title, is_series):
            raise DuplicateEntryException(
                f"'{title}' is already in the watchlist"
            )
        return self._watchlist_repo.add_by_title(title, is_series)

    def remove(self, title: str, is_series: bool) -> None:
        """Remove from watchlist.

        Raises EntryNotFoundException if not present.
        """
        if not self._watchlist_repo.delete_by_title(title, is_series):
            raise EntryNotFoundException(
                f"'{title}' is not in the watchlist"
            )

    def filter_items(self, key: Callable[[str, bool], bool]) -> list[tuple[str, bool]]:
        return [(t, s) for t, s in self.get_items() if key(t, s)]

    def get_is_series(self, title: str) -> bool | None:
        """Return is_series for the given title, or None if not found."""
        for e in self._watchlist_repo.get_all():
            if e.title == title:
                return e.is_series
        return None

    def possible_title_match(
        self, title: str, score_threshold: float = 0.7
    ) -> str | None:
        return possible_match(title, self.titles, score_threshold=score_threshold)
