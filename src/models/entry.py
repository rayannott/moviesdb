from decimal import Decimal
from enum import StrEnum

from pydantic import Field
from pydantic_extra_types.pendulum_dt import DateTime

from .mongo_base import EntryBaseModel


class EntryType(StrEnum):
    MOVIE = "MOVIE"
    SERIES = "SERIES"


class Entry(EntryBaseModel):
    title: str
    rating: Decimal
    created_dt: DateTime | None = Field(default=None)
    type: EntryType = Field(default=EntryType.MOVIE)
    notes: str = Field(default="")
    tags: set[str] = Field(default_factory=set)
    # image_ids: set[str] = Field(default_factory=set)
