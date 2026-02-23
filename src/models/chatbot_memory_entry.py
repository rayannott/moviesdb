from .mongo_base import EntryBaseModel


class ChatbotMemoryEntry(EntryBaseModel):
    item: str
