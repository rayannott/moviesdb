import re

import pytest
from bson import ObjectId
from pymongo import MongoClient

from src.mongo import Mongo

_missing = object()


@pytest.fixture(scope="session")
def mongo_client() -> MongoClient:
    """Fixture to create a MongoDB client."""
    return Mongo.client()


def test_mongo_client(mongo_client: MongoClient):
    assert mongo_client.admin.command("ping")["ok"] == 1, (
        "MongoDB client should be connected successfully."
    )


def test_entry_dicts():
    DATE_RE = re.compile(r"\d{2}.\d{2}.\d{4}")

    entry_dicts = Mongo.entries().find()
    for entry_dict in entry_dicts:
        assert isinstance(entry_dict["_id"], ObjectId), (
            f"ID should be an ObjectId in {entry_dict!r}"
        )
        title = entry_dict["title"]
        assert title, f"Title should not be empty in {entry_dict!r}"
        assert isinstance(title, str), f"Title should be a string in {entry_dict!r}"
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
            f"Date should be missing or of format dd.mm.yyyy in {entry_dict!r}"
        )


def test_watchlist_entry_dicts():
    def check_one(watchlist_entry_dict: dict):
        assert isinstance(watchlist_entry_dict["_id"], ObjectId), (
            f"ID should be an ObjectId in {watchlist_entry_dict!r}"
        )
        title = watchlist_entry_dict["title"]
        assert title, f"Title should not be empty in {watchlist_entry_dict!r}"
        assert isinstance(title, str), (
            f"Title should be a string in {watchlist_entry_dict!r}"
        )

        is_series = watchlist_entry_dict["is_series"]
        assert isinstance(is_series, bool), (
            f"is_series should be a boolean in {watchlist_entry_dict!r}"
        )

    watchlist_entry_dicts = Mongo.watchlist().db.watchlist.find()
    for watchlist_entry_dict in watchlist_entry_dicts:
        check_one(watchlist_entry_dict)
