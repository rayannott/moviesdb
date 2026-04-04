"""Derived (title, type) groups over `Entry` rows — not stored in MongoDB."""

from collections import defaultdict
from datetime import UTC, datetime, timedelta
from statistics import mean
from typing import Self

from pydantic import BaseModel

from src.models.entry import Entry, EntryType

MIN_DT = datetime(1900, 1, 1, tzinfo=UTC)

# ~three months; timedelta cannot express calendar months.
REVIEW_MIN_AGE_DAYS = 90


def _utc_for_cmp(dt: datetime | None) -> datetime:
    """UTC-aware instant for ordering; aligns naive/aware like `Entry` date validation."""
    if dt is None:
        return MIN_DT
    return dt.astimezone(UTC)


class EntryGroup(BaseModel):
    """Aggregated ratings for one (title, type) across multiple watches."""

    title: str
    ratings: list[float]
    type: EntryType
    watched_last: datetime | None = None

    @property
    def mean_rating(self) -> float:
        return mean(self.ratings)

    @classmethod
    def from_list_of_entries(cls, entries: list[Entry]) -> Self:
        """Build from a non-empty list sharing the same title and type."""
        work = list(entries)
        work.sort(key=lambda e: _utc_for_cmp(e.date))
        title = work[0].title
        typ = work[0].type
        assert all(entry.title == title for entry in work)
        assert all(entry.type == typ for entry in work)
        ratings = [entry.rating for entry in work]
        dated = [e for e in work if e.date is not None]
        watched_last = (
            max(dated, key=lambda e: _utc_for_cmp(e.date)).date if dated else None
        )
        return cls(
            title=title,
            ratings=ratings,
            type=typ,
            watched_last=watched_last,
        )

    def __str__(self) -> str:
        from_str = (
            f" (last {datetime.strftime(self.watched_last, '%d.%m.%Y')})"
            if self.watched_last
            else ""
        )
        mean_str = f"({self.mean_rating:.3f})" if len(self.ratings) > 1 else ""
        return f"{self.ratings}{mean_str} {self.title}{from_str}"


def groups_from_list_of_entries(entries: list[Entry]) -> list[EntryGroup]:
    grouped: defaultdict[tuple[str, EntryType], list[Entry]] = defaultdict(list)
    for entry in entries:
        grouped[(entry.title, entry.type)].append(entry)
    return sorted(
        [EntryGroup.from_list_of_entries(items) for items in grouped.values()],
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
    max_at = max(_utc_for_cmp(e.date) for e in dated)
    tied = [e for e in dated if _utc_for_cmp(e.date) == max_at]
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
        if getattr(last, "review_rating", None) is not None:
            continue
        if last.date is not None and _utc_for_cmp(last.date) >= cutoff:
            continue
        eg = EntryGroup.from_list_of_entries(list(group_entries))
        idx = next(i for i, e in enumerate(entries) if e.id == last.id)
        out.append((eg, last, idx))
    return out
