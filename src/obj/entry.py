from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto

from bson.objectid import ObjectId

from src.utils.utils import (
    DATE_PATTERNS,
    find_hashtags,
    parse_date,
    parse_per_season_ratings,
    remove_hashtags,
)


class Verbosity:
    _instance = None
    _verbose = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def toggle(self):
        self._verbose = not self._verbose

    def __bool__(self):
        return self._verbose


is_verbose = Verbosity()  # (now a real) singleton to toggle verbosity


class Type(Enum):
    MOVIE = auto()
    SERIES = auto()

    def to_store(self):
        return self.name

    @staticmethod
    def from_store(value):
        return Type[value]


class MalformedEntryException(Exception):
    pass


@dataclass
class Entry:
    _id: ObjectId | None = field(compare=False)
    title: str
    rating: float
    date: datetime | None
    type: Type = Type.MOVIE
    notes: str = ""
    tags: set[str] = field(default_factory=set[str])
    images: set[str] = field(default_factory=set)

    def __post_init__(self):
        self.title = self.title.strip()
        self.notes = self.notes.strip()
        self.tags.update(find_hashtags(self.notes))
        self.notes = remove_hashtags(self.notes)

    @property
    def is_series(self) -> bool:
        return self.type == Type.SERIES

    def __repr__(self):
        return self._repr(bool(is_verbose))

    def __format__(self, format_spec: str) -> str:
        if format_spec == "v":
            return self._repr(True)
        return self._repr(False)

    def _repr(self, verbose: bool) -> str:
        note_str = f": {self.notes}" if self.notes else ""
        type_str = f" ({self.type.name.lower()})" if self.type != Type.MOVIE else ""
        watched_date_str = f" ({self.date.strftime('%d.%m.%Y')})" if self.date else ""
        tags_str = f" [{' '.join(f'󰓹 {t}' for t in self.tags)}]" if self.tags else ""
        if not verbose:
            note_str = ""
        return f"[{self.rating:.2f}] {self.title}{type_str}{watched_date_str}{note_str}{tags_str}"

    def as_dict(self):
        return (
            {
                "title": self.title,
                "rating": self.rating,
            }
            | ({"type": self.type.to_store()} if self.type != Type.MOVIE else {})
            | ({"notes": self.notes} if self.notes else {})
            | ({"date": self.date.strftime("%d.%m.%Y")} if self.date else {})
            | ({"tags": sorted(self.tags)} if self.tags else {})
            | ({"images": sorted(self.images)} if self.images else {})
        )

    def __lt__(self, other: "Entry") -> bool:
        if self.date is None and other.date is None:
            return (len(self.images), len(self.tags), len(self.notes), self.title) < (
                len(other.images),
                len(other.tags),
                len(other.notes),
                other.title,
            )
        if self.date is None:
            return True
        if other.date is None:
            return False
        return self.date < other.date

    @classmethod
    def from_dict(cls, data: dict) -> "Entry":
        watched_date_str = data.get("date")
        return cls(
            _id=ObjectId(data["_id"]),
            title=data["title"],
            rating=data["rating"],
            type=Type.from_store(data["type"]) if "type" in data else Type.MOVIE,
            date=datetime.strptime(watched_date_str, "%d.%m.%Y")
            if watched_date_str is not None
            else None,
            notes=data.get("notes", ""),
            tags=set(data.get("tags", [])),
            images=set(data.get("images", [])),
        )

    def get_per_season(self) -> list[float | None]:
        return parse_per_season_ratings(self.notes)

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
            date = datetime.now()
        elif when.lower() in {"none", "-", ""}:
            date = None
        else:
            if (date := parse_date(when)) is None:
                raise MalformedEntryException(
                    f"Bad date format {date}; should be {DATE_PATTERNS}."
                )
        return date

    @staticmethod
    def parse_type(type: str) -> Type:
        if not type:
            return Type.MOVIE
        try:
            return Type[type.upper()]
        except KeyError:
            raise MalformedEntryException(f"Unknown type: {type}")

    def attach_image(self, s3_id: str) -> bool:
        """
        Attach an image to the entry.
        :param s3_id: S3 ID of the image.
        :return: True if the image was attached, False if it was already attached.
        """
        if s3_id in self.images:
            return False
        self.images.add(s3_id)
        return True

    def detach_image(self, s3_id: str) -> bool:
        """
        Detach an image from the entry.
        :param s3_id: S3 ID of the image.
        :return: True if the image was detached, False if it was not attached.
        """
        if s3_id not in self.images:
            return False
        self.images.remove(s3_id)
        return True


def build_tags(entries: list[Entry]):
    tags: defaultdict[str, list[Entry]] = defaultdict(list)
    for entry in entries:
        for tag in entry.tags:
            tags[tag].append(entry)
    return tags
