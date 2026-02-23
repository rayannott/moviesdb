import random
from collections import defaultdict
from dataclasses import dataclass

from src.exceptions import EntryNotFoundException
from src.models.entry import Entry, build_tags
from src.obj.entry_group import EntryGroup, groups_from_list_of_entries
from src.repos.entries import EntriesRepo
from src.repos.watchlist_entries import WatchlistEntriesRepo
from src.utils.utils import TAG_WATCH_AGAIN, possible_match, replace_tag_alias


@dataclass
class StatsResult:
    """Plain data container for statistics."""

    total: int
    movie_ratings: list[float]
    series_ratings: list[float]
    groups: list[EntryGroup]
    watchlist_count: int
    watchlist_movies_count: int
    watchlist_series_count: int


class EntryService:
    """Business logic for movie/series entries."""

    def __init__(
        self,
        entries_repo: EntriesRepo,
        watchlist_repo: WatchlistEntriesRepo,
    ) -> None:
        self._entries_repo = entries_repo
        self._watchlist_repo = watchlist_repo

    def get_entries(self) -> list[Entry]:
        """Return all entries sorted by date."""
        return sorted(self._entries_repo.get_all())

    def add_entry(self, entry: Entry) -> Entry:
        return self._entries_repo.add(entry)

    def update_entry(self, entry: Entry) -> None:
        self._entries_repo.update(entry)

    def delete_entry(self, entry_id: str) -> None:
        """Delete an entry by id.

        Raises EntryNotFoundException if the entry does not exist.
        """
        if not self._entries_repo.delete(entry_id):
            raise EntryNotFoundException(f"Entry {entry_id} not found")

    def get_entry(self, entry_id: str) -> Entry:
        return self._entries_repo.get(entry_id)

    def find_exact_matches(
        self, title: str, *, ignore_case: bool = True
    ) -> list[tuple[int, Entry]]:
        entries = self.get_entries()

        def str_eq(s1: str, s2: str) -> bool:
            return s1.lower() == s2.lower() if ignore_case else s1 == s2

        return [(i, e) for i, e in enumerate(entries) if str_eq(title, e.title)]

    def find_substring_matches(self, title: str) -> list[tuple[int, Entry]]:
        entries = self.get_entries()
        return [
            (i, e)
            for i, e in enumerate(entries)
            if title.lower() in e.title.lower() and title.lower() != e.title.lower()
        ]

    def find_by_note(self, substring: str) -> list[tuple[int, Entry]]:
        entries = self.get_entries()
        return [
            (i, e)
            for i, e in enumerate(entries)
            if substring.lower() in e.notes.lower()
        ]

    def get_groups(self) -> list[EntryGroup]:
        return groups_from_list_of_entries(self.get_entries())

    def get_random_entries(self, n: int = 1, tag: str | None = None) -> list[Entry]:
        entries = self.get_entries()
        if tag:
            tag = replace_tag_alias(tag)
            entries = [e for e in entries if tag in e.tags]
        if not entries:
            return []
        n = min(len(entries), n)
        return random.sample(entries, k=n)

    def get_stats(self) -> StatsResult:
        entries = self.get_entries()
        watchlist = self._watchlist_repo.get_all()
        return StatsResult(
            total=len(entries),
            movie_ratings=[e.rating for e in entries if not e.is_series],
            series_ratings=[e.rating for e in entries if e.is_series],
            groups=self.get_groups(),
            watchlist_count=len(watchlist),
            watchlist_movies_count=sum(1 for w in watchlist if not w.is_series),
            watchlist_series_count=sum(1 for w in watchlist if w.is_series),
        )

    def get_tags(self) -> defaultdict[str, list[Entry]]:
        return build_tags(self.get_entries())

    def add_tag(self, entry: Entry, tag_name: str) -> bool:
        """Add tag to entry; returns False if already present."""
        tag_name = replace_tag_alias(tag_name)
        if tag_name in entry.tags:
            return False
        entry.tags.add(tag_name)
        self.update_entry(entry)
        return True

    def remove_tag(self, entry: Entry, tag_name: str) -> bool:
        """Remove tag from entry; returns False if not present."""
        tag_name = replace_tag_alias(tag_name)
        if tag_name not in entry.tags:
            return False
        entry.tags.remove(tag_name)
        self.update_entry(entry)
        return True

    def process_watch_again_on_add(self, new_entry: Entry) -> list[Entry]:
        """Remove watch-again tag from previous entries with the same title.

        Returns the modified entries.
        """
        entries = self.get_entries()
        modified: list[Entry] = []
        for e in entries:
            if (
                e.title == new_entry.title
                and e.type == new_entry.type
                and TAG_WATCH_AGAIN in e.tags
                and e.id != new_entry.id
            ):
                e.tags.remove(TAG_WATCH_AGAIN)
                self.update_entry(e)
                modified.append(e)
        return modified

    def remove_from_watchlist_on_add(self, entry: Entry) -> bool:
        """Remove from watchlist after adding to DB. Returns True if removed."""
        return self._watchlist_repo.delete_by_title(entry.title, entry.is_series)

    def entry_by_idx(self, idx: int | str) -> Entry | None:
        """Get entry by sorted-list index. Returns None on invalid index."""
        try:
            return self.get_entries()[int(idx)]
        except (ValueError, IndexError):
            return None

    def entry_by_idx_or_title(self, idx_title: str | int) -> Entry | None:
        """Get entry by index or title.

        If title matches multiple, returns the most recent.
        """
        by_idx = self.entry_by_idx(idx_title)
        if by_idx:
            return by_idx
        by_title = self.find_exact_matches(str(idx_title))
        if by_title:
            return by_title[-1][1]
        return None

    def possible_title_match(
        self, title: str, score_threshold: float = 0.65
    ) -> str | None:
        titles = {e.title for e in self.get_entries()}
        return possible_match(title, titles, score_threshold=score_threshold)
