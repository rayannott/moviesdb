from pymongo.collection import Collection
from pymongo.mongo_client import MongoClient

from src.models.entry import Entry


class Mongo:
    def __init__(self, client: MongoClient):
        self._client = client

    @property
    def entries(self) -> Collection:
        return self._client.db.entries

    @property
    def watchlist(self) -> Collection:
        return self._client.db.watchlist

    @property
    def aimemory(self) -> Collection:
        return self._client.db.aimemory

    @property
    def botguests(self) -> Collection:
        return self._client.db.botguests
