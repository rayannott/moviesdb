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


def last_watched_entry(entries: list[Entry]) -> Entry | None:
    """Newest watch by `date`; ties broken by smallest `id`."""
    dates = [d for e in entries if (d := e.date) is not None]
    if not dates:
        return None
    max_dt = max(dates)
    tied = [e for e in entries if e.date == max_dt]
    return min(tied, key=lambda e: e.id)


def review_eligible_groups(
    entries: list[Entry],
    *,
    min_age_days: int = REVIEW_MIN_AGE_DAYS,
) -> list[tuple[EntryGroup, Entry, int]]:
    """Groups whose last-watched entry has no review_rating and last watch older than cutoff."""
    cutoff = datetime.now(UTC) - timedelta(days=min_age_days)
    by_key: defaultdict[tuple[str, EntryType], list[Entry]] = defaultdict(list)
    for e in entries:
        by_key[(e.title, e.type)].append(e)
    out: list[tuple[EntryGroup, Entry, int]] = []
    for group_entries in by_key.values():
        last = last_watched_entry(group_entries)
        if last is None or last.review_rating is not None:
            continue
        wl = last.date
        assert wl is not None
        if wl >= cutoff:
            continue
        eg = EntryGroup.from_list_of_entries(list(group_entries))
        idx = next(i for i, e in enumerate(entries) if e.id == last.id)
        out.append((eg, last, idx))
    return out
