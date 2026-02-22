from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from statistics import mean

from src.models.entry import Entry, EntryType


@dataclass
class EntryGroup:
    title: str
    ratings: list[float]
    type: EntryType
    watched_last: datetime | None

    @staticmethod
    def from_list_of_entries(entries: list[Entry]) -> "EntryGroup":
        entries.sort(key=lambda e: e.date if e.date else datetime.min)
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
