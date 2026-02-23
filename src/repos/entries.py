from typing import Any

from src.models.entry import Entry
from src.repos.mongo_base import MongoRepo


class EntriesRepo(MongoRepo[Entry]):
    collection_name = "entries"

    def _serialize(self, entry: Entry) -> dict[str, Any]:
        return entry.to_mongo_dict()
