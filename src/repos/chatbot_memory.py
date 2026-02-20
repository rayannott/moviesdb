from bson import ObjectId
from pymongo.collection import Collection
from pymongo.mongo_client import MongoClient

from src.models.chatbot_memory_entry import ChatbotMemoryEntry


class ChatbotMemoryEntriesRepo:
    def __init__(self, client: MongoClient):
        self._client = client

    @property
    def entries(self) -> Collection:
        return self._client.db.aimemory

    def add_entry(self, entry: ChatbotMemoryEntry) -> ChatbotMemoryEntry:
        id = self.entries.insert_one(entry.model_dump())
        entry.id = str(id.inserted_id)
        return entry
