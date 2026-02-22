"""Tests for MongoDB data integrity via the repository layer."""

import re

import pytest
from bson import ObjectId

from src.dependencies import Container

_missing = object()


@pytest.fixture(scope="session")
def container() -> Container:
    """Fixture to create a DI container."""
    return Container()


def test_mongo_client(container: Container) -> None:
    """Verify MongoDB client connectivity."""
    client = container.mongo_client()
    assert client.admin.command("ping")["ok"] == 1, (
        "MongoDB client should be connected successfully."
    )


def test_entry_dicts(container: Container) -> None:
    """Validate raw entry documents in MongoDB."""
    DATE_RE = re.compile(r"\d{2}.\d{2}.\d{4}")

    entries_repo = container.entries_repo()
    entry_dicts = entries_repo.collection.find()
    for entry_dict in entry_dicts:
        assert isinstance(entry_dict["_id"], ObjectId), (
            f"ID should be an ObjectId in {entry_dict!r}"
        )
        title = entry_dict["title"]
        assert title, f"Title should not be empty in {entry_dict!r}"
        assert isinstance(title, str), (
            f"Title should be a string in {entry_dict!r}"
        )
        assert isinstance(entry_dict["rating"], float), (
            f"Rating should be a float in {entry_dict!r}"
        )
        tags_ = entry_dict.get("tags", _missing)
        assert tags_ is _missing or isinstance(tags_, list), (
            f"Tags should be missing or a list in {entry_dict!r}"
        )
        type_ = entry_dict.get("type", _missing)
        assert type_ is _missing or type_ == "SERIES", (
            f"Type should be missing (=MOVIE) or 'SERIES' in {entry_dict!r}"
        )
        date_ = entry_dict.get("date", _missing)
        assert date_ is _missing or DATE_RE.match(date_), (
            f"Date should be missing or dd.mm.yyyy in {entry_dict!r}"
        )


def test_watchlist_entry_dicts(container: Container) -> None:
    """Validate raw watchlist documents in MongoDB."""

    def check_one(watchlist_entry_dict: dict) -> None:
        assert isinstance(watchlist_entry_dict["_id"], ObjectId), (
            f"ID should be an ObjectId in {watchlist_entry_dict!r}"
        )
        title = watchlist_entry_dict["title"]
        assert title, (
            f"Title should not be empty in {watchlist_entry_dict!r}"
        )
        assert isinstance(title, str), (
            f"Title should be a string in {watchlist_entry_dict!r}"
        )
        is_series = watchlist_entry_dict["is_series"]
        assert isinstance(is_series, bool), (
            f"is_series should be a boolean in {watchlist_entry_dict!r}"
        )

    watchlist_repo = container.watchlist_entries_repo()
    watchlist_entry_dicts = watchlist_repo.collection.find()
    for watchlist_entry_dict in watchlist_entry_dicts:
        check_one(watchlist_entry_dict)
