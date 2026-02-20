from .mongo_base import EntryBaseModel


class BotGuestEntry(EntryBaseModel):
    username: str
