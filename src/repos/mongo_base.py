from bson import ObjectId
from pymongo.collection import Collection
from pymongo.mongo_client import MongoClient

from src.models.mongo_base import EntryBaseModel
from src.exceptions import EntryNotFoundException


class MongoRepo[EntryT: EntryBaseModel]:
    def __init__(self, client: MongoClient, model_cls: type[EntryT]):
        self._client = client
        self._model_cls = model_cls

    @property
    def entries(self) -> Collection:
        return self._client.db.entries

    def add_entry(self, entry: EntryT) -> EntryT:
        id = self.entries.insert_one(entry.model_dump())
        entry.id = str(id.inserted_id)
        return entry

    def get_entry(self, id: ObjectId) -> EntryT:
        entry = self.entries.find_one({"_id": id})
        if not entry:
            raise EntryNotFoundException(f"Entry with id {id} not found")
        return self._model_cls.model_validate(entry)

    def get_entries(self) -> list[EntryT]:
        entries = self.entries.find()
        return [self._model_cls.model_validate(entry) for entry in entries]
