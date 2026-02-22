from collections import defaultdict
from datetime import datetime
from enum import StrEnum
from typing import Any, Self

from pydantic import Field, field_validator, model_validator

from src.exceptions import MalformedEntryException
from src.models.mongo_base import EntryBaseModel
from src.utils.utils import (
    DATE_PATTERNS,
    find_hashtags,
    parse_date as _parse_date_str,
    parse_per_season_ratings,
    remove_hashtags,
)


class EntryType(StrEnum):
    MOVIE = "MOVIE"
    SERIES = "SERIES"


class Entry(EntryBaseModel):
    """A movie or series entry in the database."""

    title: str
    rating: float
    date: datetime | None = Field(default=None)
    type: EntryType = Field(default=EntryType.MOVIE)
    notes: str = Field(default="")
    tags: set[str] = Field(default_factory=set)
    image_ids: set[str] = Field(default_factory=set, validation_alias="images")

    @field_validator("date", mode="before")
    @classmethod
    def validate_date(cls, v: Any) -> datetime | None:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            parsed = _parse_date_str(v)
            if parsed is None:
                raise ValueError(f"Cannot parse date: {v}")
            return parsed
        return v

    @field_validator("tags", mode="before")
    @classmethod
    def validate_tags(cls, v: Any) -> set[str]:
        if isinstance(v, list):
            return set(v)
        return v

    @field_validator("type", mode="before")
    @classmethod
    def validate_type(cls, v: Any) -> str:
        if isinstance(v, str):
            return v.upper()
        return v

    @model_validator(mode="after")
    def process_notes_and_tags(self) -> Self:
        """Extract hashtags from notes and merge into tags."""
        self.title = self.title.strip()
        hashtags = find_hashtags(self.notes)
        self.tags.update(hashtags)
        self.notes = remove_hashtags(self.notes).strip()
        return self

    @property
    def is_series(self) -> bool:
        return self.type == EntryType.SERIES

    def __lt__(self, other: "Entry") -> bool:
        if self.date is None and other.date is None:
            return (
                len(self.image_ids),
                len(self.tags),
                len(self.notes),
                self.title,
            ) < (
                len(other.image_ids),
                len(other.tags),
                len(other.notes),
                other.title,
            )
        if self.date is None:
            return True
        if other.date is None:
            return False
        return self.date < other.date

    def __hash__(self) -> int:
        return hash(self.id) if self.id else hash((self.title, self.rating, self.type))

    def __repr__(self) -> str:
        return self._text_repr(verbose=False)

    def __format__(self, format_spec: str) -> str:
        return self._text_repr(verbose=(format_spec == "v"))

    def _text_repr(self, verbose: bool) -> str:
        note_str = f": {self.notes}" if self.notes and verbose else ""
        type_str = (
            f" ({self.type.name.lower()})" if self.type != EntryType.MOVIE else ""
        )
        date_str = f" ({self.date.strftime('%d.%m.%Y')})" if self.date else ""
        tags_str = f" [{' '.join(f'󰓹 {t}' for t in self.tags)}]" if self.tags else ""
        return (
            f"[{self.rating:.2f}] {self.title}{type_str}{date_str}{note_str}{tags_str}"
        )

    def to_mongo_dict(self) -> dict[str, Any]:
        """Serialize to MongoDB-compatible dict (matches legacy storage format)."""
        d: dict[str, Any] = {"title": self.title, "rating": self.rating}
        if self.type != EntryType.MOVIE:
            d["type"] = self.type.value
        if self.notes:
            d["notes"] = self.notes
        if self.date:
            d["date"] = self.date.strftime("%d.%m.%Y")
        if self.tags:
            d["tags"] = sorted(self.tags)
        if self.image_ids:
            d["images"] = sorted(self.image_ids)
        return d

    def get_per_season(self) -> list[float | None]:
        return parse_per_season_ratings(self.notes)

    def attach_image(self, s3_id: str) -> bool:
        """Attach an image; returns False if already attached."""
        if s3_id in self.image_ids:
            return False
        self.image_ids.add(s3_id)
        return True

    def detach_image(self, s3_id: str) -> bool:
        """Detach an image; returns False if not attached."""
        if s3_id not in self.image_ids:
            return False
        self.image_ids.remove(s3_id)
        return True

    @staticmethod
    def parse_rating(rating_str: str) -> float:
        try:
            rating = float(rating_str)
        except ValueError:
            raise MalformedEntryException(f"Not a number: {rating_str}")
        if rating <= 0 or rating > 10:
            raise MalformedEntryException(
                f"Rating out of range (0 < rating <= 10): {rating}"
            )
        return rating

    @staticmethod
    def parse_date(when: str) -> datetime | None:
        if when in {"now", "today"}:
            return datetime.now()
        if when.lower() in {"none", "-", ""}:
            return None
        date = _parse_date_str(when)
        if date is None:
            raise MalformedEntryException(
                f"Bad date format {when}; should be {DATE_PATTERNS}."
            )
        return date

    @staticmethod
    def parse_type(type_str: str) -> "EntryType":
        if not type_str:
            return EntryType.MOVIE
        try:
            return EntryType[type_str.upper()]
        except KeyError:
            raise MalformedEntryException(f"Unknown type: {type_str}")


def build_tags(entries: list[Entry]) -> defaultdict[str, list[Entry]]:
    """Group entries by their tags."""
    tags: defaultdict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        for tag in entry.tags:
            tags[tag].append(entry)
    return tags
