from src.models.chatbot_memory_entry import ChatbotMemoryEntry
from src.repos.mongo_base import MongoRepo


class ChatbotMemoryEntriesRepo(MongoRepo[ChatbotMemoryEntry]):
    collection_name = "aimemory"

    def add_item(self, item: str) -> ChatbotMemoryEntry:
        entry = ChatbotMemoryEntry(item=item)
        return self.add(entry)

    def get_items(self) -> list[tuple[str, str]]:
        """Return (id, item) pairs for all memory entries."""
        return [(e.id, e.item) for e in self.get_all()]
