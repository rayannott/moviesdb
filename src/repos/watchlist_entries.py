from bson import ObjectId
from pymongo.collection import Collection
from pymongo.mongo_client import MongoClient

from src.models.watchlist_entry import WatchlistEntry


class WatchlistEntriesRepo:
    def __init__(self, client: MongoClient):
        self._client = client

    @property
    def entries(self) -> Collection:
        return self._client.db.watchlist

    def add_entry(self, entry: WatchlistEntry) -> WatchlistEntry:
        id = self.entries.insert_one(entry.model_dump())
        entry.id = str(id.inserted_id)
        return entry
