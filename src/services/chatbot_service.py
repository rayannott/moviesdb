from bson import ObjectId

from src.repos.chatbot_memory import ChatbotMemoryEntriesRepo


class ChatbotService:
    """Business logic for chatbot memory management."""

    def __init__(self, memory_repo: ChatbotMemoryEntriesRepo) -> None:
        self._memory_repo = memory_repo

    def get_memory_items(self) -> list[tuple[str, str]]:
        """Return (id, item) pairs."""
        return self._memory_repo.get_items()

    def add_memory(self, text: str) -> str:
        """Store a memory item; returns its id."""
        entry = self._memory_repo.add_item(text)
        return entry.id

    def delete_memory(self, id_or_prefix: str) -> tuple[bool, str | None]:
        """Delete a memory by full id or prefix.

        Returns (success, deleted_id).
        """
        for mem_id, _ in self.get_memory_items():
            if id_or_prefix in mem_id:
                ok = self._memory_repo.delete(ObjectId(mem_id))
                return ok, mem_id
        return False, None
