"""Backward-compatibility re-exports from the unified models."""

from src.exceptions import MalformedEntryException
from src.models.entry import Entry, EntryType, build_tags

# Alias for backward compatibility: old code uses Type.MOVIE / Type.SERIES
Type = EntryType


class Verbosity:
    """Singleton to toggle verbose display mode (UI concern)."""

    _instance = None
    _verbose = False

    def __new__(cls) -> "Verbosity":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def toggle(self) -> None:
        self._verbose = not self._verbose

    def __bool__(self) -> bool:
        return self._verbose


is_verbose = Verbosity()

__all__ = [
    "Entry",
    "EntryType",
    "Type",
    "MalformedEntryException",
    "Verbosity",
    "is_verbose",
    "build_tags",
]
