from typing import Any

from bson import ObjectId
from pymongo.collection import Collection
from pymongo.mongo_client import MongoClient

from src.exceptions import EntryNotFoundException
from src.models.mongo_base import EntryBaseModel


class MongoRepo[EntryT: EntryBaseModel]:
    """Generic MongoDB repository with CRUD operations."""

    collection_name: str

    def __init__(self, client: MongoClient, model_cls: type[EntryT]) -> None:
        self._client = client
        self._model_cls = model_cls

    @property
    def collection(self) -> Collection:
        return self._client.db[self.collection_name]

    def _serialize(self, entry: EntryT) -> dict[str, Any]:
        """Serialize model to dict for MongoDB storage.

        Subclasses can override for custom serialization (e.g., Entry.to_mongo_dict).
        """
        return entry.model_dump(exclude={"id"})

    def _deserialize(self, data: dict[str, Any]) -> EntryT:
        return self._model_cls.model_validate(data)

    def add(self, entry: EntryT) -> EntryT:
        result = self.collection.insert_one(self._serialize(entry))
        entry.id = str(result.inserted_id)
        return entry

    def get(self, id: str | ObjectId) -> EntryT:
        oid = ObjectId(id) if isinstance(id, str) else id
        data = self.collection.find_one({"_id": oid})
        if not data:
            raise EntryNotFoundException(
                f"{self._model_cls.__name__} with id {id} not found"
            )
        return self._deserialize(data)

    def get_all(self) -> list[EntryT]:
        return [self._deserialize(doc) for doc in self.collection.find()]

    def update(self, entry: EntryT) -> None:
        if not entry.id:
            raise ValueError("Cannot update entry without an id")
        self.collection.replace_one({"_id": ObjectId(entry.id)}, self._serialize(entry))

    def delete(self, id: str | ObjectId) -> bool:
        oid = ObjectId(id) if isinstance(id, str) else id
        return self.collection.delete_one({"_id": oid}).deleted_count == 1

    def find_by(self, **kwargs: Any) -> list[EntryT]:
        return [self._deserialize(doc) for doc in self.collection.find(kwargs)]

    def delete_by(self, **kwargs: Any) -> bool:
        return self.collection.delete_one(kwargs).deleted_count == 1
