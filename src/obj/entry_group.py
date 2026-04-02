from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from statistics import mean

from src.models.entry import Entry, EntryType


MIN_DT = datetime(1900, 1, 1, tzinfo=UTC)

# ~three months; timedelta cannot express calendar months.
REVIEW_MIN_AGE_DAYS = 90


@dataclass
class EntryGroup:
    title: str
    ratings: list[float]
    type: EntryType
    watched_last: datetime | None

    @staticmethod
    def from_list_of_entries(entries: list[Entry]) -> "EntryGroup":
        entries.sort(key=lambda e: e.date if e.date else MIN_DT)
        title = entries[0].title
        type = entries[0].type
        assert all(entry.title == title for entry in entries)
        assert all(entry.type == type for entry in entries)
        ratings = [entry.rating for entry in entries]
        watched_last = max(
            [entry.date for entry in entries if entry.date is not None], default=None
        )
        return EntryGroup(title, ratings, type, watched_last)

    def __str__(self) -> str:
        from_str = (
            f" (last {datetime.strftime(self.watched_last, '%d.%m.%Y')})"
            if self.watched_last
            else ""
        )
        mean_str = f"({self.mean_rating:.3f})" if len(self.ratings) > 1 else ""
        return f"{self.ratings}{mean_str} {self.title}{from_str}"

    @property
    def mean_rating(self) -> float:
        return mean(self.ratings)


def groups_from_list_of_entries(entries: list[Entry]) -> list[EntryGroup]:
    grouped: defaultdict[tuple[str, EntryType], list[Entry]] = defaultdict(list)
    for entry in entries:
        grouped[(entry.title, entry.type)].append(entry)
    return sorted(
        [EntryGroup.from_list_of_entries(entries) for entries in grouped.values()],
        key=lambda group: group.mean_rating,
        reverse=True,
    )


def partition_by_title_group(entries: list[Entry]) -> list[list[Entry]]:
    """Split entries into disjoint lists, one per (title, type) group."""
    grouped: defaultdict[tuple[str, EntryType], list[Entry]] = defaultdict(list)
    for entry in entries:
        grouped[(entry.title, entry.type)].append(entry)
    return list(grouped.values())


def last_watched_entry(entries: list[Entry]) -> Entry:
    """Newest watch by `date`; ties broken by smallest `id`.

    If no entry has a date, falls back to the entry with the smallest id.
    """
    dated = [e for e in entries if e.date is not None]
    if not dated:
        return min(entries, key=lambda e: e.id)
    max_dt = max(e.date for e in dated)  # type: ignore[arg-type]
    tied = [e for e in dated if e.date == max_dt]
    return min(tied, key=lambda e: e.id)


def review_eligible_groups(
    entries: list[Entry],
    *,
    min_age_days: int = REVIEW_MIN_AGE_DAYS,
) -> list[tuple[EntryGroup, Entry, int]]:
    """Groups whose last-watched entry has no review_rating and is old enough.

    Entries without a date are treated as infinitely old (always eligible).
    """
    cutoff = datetime.now(UTC) - timedelta(days=min_age_days)
    out: list[tuple[EntryGroup, Entry, int]] = []
    for group_entries in partition_by_title_group(entries):
        last = last_watched_entry(group_entries)
        if last.review_rating is not None:
            continue
        if last.date is not None and last.date >= cutoff:
            continue
        eg = EntryGroup.from_list_of_entries(list(group_entries))
        idx = next(i for i, e in enumerate(entries) if e.id == last.id)
        out.append((eg, last, idx))
    return out
